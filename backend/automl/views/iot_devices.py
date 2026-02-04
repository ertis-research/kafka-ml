import os
import traceback
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

import json

from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from loguru import logger

from rest_framework import status
from rest_framework import generics
from rest_framework.response import Response

from automl.serializers import MLModelSerializer
from automl.serializers import IoTDeviceSerializer

from automl.models import MLModel, TrainingResult, Inference, IoTDevice

import paho.mqtt.publish as publish

import paho.mqtt.client as mqtt


def generate_device_backlog_config(device) -> str:
    """Generates the backlog for the IoT device.
    Args:
        device (IoTDevice): The IoT device information.
    Returns:
        str: The backlog configuration string.
    """
    backlog = f"""Backlog DeviceName {device["token"]}; FriendlyName {device["friendly_name"]}; MqttHost {device["mqtt_address"]}; MqttPort {device["mqtt_port"]}; MqttUser {device["mqtt_username"]}; MqttPassword {device["mqtt_password"]}; Topic {device["token"]}; FullTopic kafkaml/iot/%topic%/%prefix%/ ; MqttClient {device["token"]}; Hostname {device["token"]}; SetOption53 1 """

    # Extra_Backlog = "IPAddress1 192.168.5.156; IPAddress2 192.168.5.1; IPAddress3 255.255.255.0; IPAddress4 192.168.49.4; IPAddress5 150.214.40.1; SSID1 husky; Password1 huskyhusky; Webserver 2; WebPassword ertis;"

    return backlog

def generate_download_berry_script(url:str, device:IoTDevice) -> str:
    """Generates the berry script for the IoT device.
    Args:
        url (str): The URL of the server.
        device (IoTDevice): The IoT device information.
    Returns:
        str: The command with script to execute.
    """
    berry_script = f"""
    def urlfetch(url,file);
        if file==nil;
            import string;
            file=string.split(url,'/').pop();
        end; var wc=webclient();
        wc.begin(url);
        var st=wc.GET();
        if st!=200
            st = 'connection_error';
            print('status: '+str(st));
            # raise 'connection_error','status: '+str(st)
        end;
        st='Fetched '+str(wc.write_file(file));
        print(url,st); wc.close();
        return st;
    end;
    tasmota.cmd('UfsDelete autoexec.be');
    tasmota.cmd('UfsDelete model.tflite');
    urlfetch('{url}/api/iot-devices/{device.token}/autoexec.be');
    urlfetch('{url}/api/iot-devices/{device.token}/model.tflite');
    tasmota.cmd('Restart 1');
    """

    return ' '.join(line.strip() for line in berry_script.strip().splitlines() if line.strip() and not line.strip().startswith('#'))



def check_device_status(device):
    """Handles MQTT connection and checks status asynchronously"""
    status_received = {"status": "disconnected"}

    try:
        client = mqtt.Client()

        def on_connect(client, userdata, flags, rc):
            """Subscribe and request status on connect"""
            if rc == 0:
                logger.debug(f"[{device['token']}] MQTT connected")
                client.subscribe(f"kafkaml/iot/{device['token']}/stat/STATUS1")
                client.publish(f"kafkaml/iot/{device['token']}/cmnd/Status", "1")
            else:
                logger.warning(f"[{device['token']}] MQTT connection failed: {rc}")

        def on_message(client, userdata, message):
            """Handle received status message"""
            logger.debug(f"[{device['token']}] MQTT message: {message.topic} -> {message.payload}")
            if message.topic == f"kafkaml/iot/{device['token']}/stat/STATUS1":
                status_received["status"] = "connected"
            client.disconnect()  # Disconnect after getting status

        client.on_connect = on_connect
        client.on_message = on_message

        client.username_pw_set(device["mqtt_username"], device["mqtt_password"])
        client.connect(device["mqtt_address"], device["mqtt_port"], 60)

        client.loop_start()
        time.sleep(0.5)  # Give it a short time window to receive status
        client.loop_stop()

    except Exception as e:
        logger.error(f"[{device['token']}] MQTT error: {e}")

    return device["id"], status_received["status"]


class IoTDeviceList(generics.ListCreateAPIView):
    """View to get the list of IoT devices and create a new device.

    URL: /iot-devices
    """

    queryset = IoTDevice.objects.all()
    serializer_class = IoTDeviceSerializer

    def get(self, request, *args, **kwargs):
        try:
            response = super().get(request, *args, **kwargs)
            devices = response.data

            # Use ThreadPoolExecutor to run status checks in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                status_results = dict(executor.map(check_device_status, devices))

            # Update device list with status results
            for device in devices:
                device["status"] = status_results.get(device["id"], "disconnected")
                device["backlog"] = generate_device_backlog_config(device)

            return Response(devices)
        except Exception as e:
            logger.error(f"Error fetching IoT devices: {e}")
            return HttpResponse("Error fetching IoT devices.", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def send_mqtt_message_to_tasmota(device: IoTDevice, cmnd: str, payload: str) -> None:
    """Sends a message to the Tasmota device using MQTT.

    Args:
        device (IoTDevice): The IoT device to send the message to.
        cmnd (str): The MQTT command (appended to the topic).
        payload (str): The payload to send.
    """
    topic = f"kafkaml/iot/{device.token}/cmnd/{cmnd}"
    try:
        publish.single(
            topic=topic,
            payload=payload,
            hostname=device.mqtt_address,
            port=device.mqtt_port,
            auth={
                "username": device.mqtt_username,
                "password": device.mqtt_password,
            },
            qos=1,  # Optionally ensure at-least-once delivery
            retain=False,
        )
        logger.info(f"MQTT message sent to device {device.token} on topic {topic}")
    except Exception as e:
        logger.error(f"Failed to send MQTT message to device {device.token}: {e}")


class IotDeviceDeploy(generics.GenericAPIView):
    """View to deploy a new IoT device.

    URL: /results/inference-iot
    """

    def post(self, request, *args, **kwargs):
        try:
            try:
                data: Dict = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return HttpResponse("Invalid JSON.", status=status.HTTP_400_BAD_REQUEST)

            berry_script: str = data.get("code")
            device_tokens: List[str] = data.get("device_token", [])
            model_result_id: int = data.get("model_result")
            apply_int_quant: bool = data.get("applyIntQuant", False)

            if not berry_script or not device_tokens or not model_result_id:
                return HttpResponse(
                    "Missing required fields: 'code', 'device_token', or 'model_result'.",
                    status=400,
                )

            frontend_url: str = request.headers.get("Origin", settings.FRONTEND_URL)

            # Validate model result
            try:
                training_result = TrainingResult.objects.get(pk=model_result_id)
            except TrainingResult.DoesNotExist:
                return HttpResponse("Model result not found.", status=status.HTTP_404_NOT_FOUND)

            # Validate devices
            devices_qs = IoTDevice.objects.filter(token__in=device_tokens)
            devices: List[IoTDevice] = list(devices_qs)
            if not devices:
                return HttpResponse("No valid devices found.", status=status.HTTP_404_NOT_FOUND)

            # TFLite conversion config
            tflite_parser_config = {
                "applyQuantization": apply_int_quant,
                "quantizationType": "int8" if apply_int_quant else "",
                "modelDeploymentId": training_result.deployment_id if apply_int_quant else "",
                "dataControlTopic": settings.CONTROL_TOPIC if apply_int_quant else "",
                "dataBootstrapServers": settings.BOOTSTRAP_SERVERS if apply_int_quant else "",
            }

            # Read model file
            model_filename = f"{model_result_id}.h5"
            model_file_path = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR, model_filename)
            if not os.path.exists(model_file_path):
                return HttpResponse("Model file not found.", status=status.HTTP_404_NOT_FOUND)

            with open(model_file_path, "rb") as f:
                model_data = f.read()

            # TensorFlow executor call
            try:
                resp = requests.post(
                    settings.TENSORFLOW_EXECUTOR_URL + "/convert_to_tflite/",
                    files={model_filename: model_data},
                    data=tflite_parser_config,
                    timeout=30,
                )
            except requests.RequestException as e:
                logger.error(f"TensorFlow executor error: {e}")
                return HttpResponse("Error contacting model conversion service.", status=503)

            if resp.status_code != 200:
                logger.warning(f"Model conversion failed: {resp.status_code} - {resp.text}")
                return HttpResponse("Model conversion failed.", status=status.HTTP_400_BAD_REQUEST)

            # Save TFLite model to file
            tflite_model_path = os.path.join(
                settings.MEDIA_ROOT, settings.TFLITE_PARSED_MODELS_DIR, f"{model_result_id}.tflite"
            )
            with open(tflite_model_path, "wb") as f:
                f.write(resp.content)

            # Deploy model and script to each device
            for device in devices:
                device_path = os.path.join(settings.DEVICES_ROOT, device.token)
                os.makedirs(device_path, exist_ok=True)

                with open(os.path.join(device_path, "model.tflite"), "wb") as f:
                    f.write(resp.content)

                with open(os.path.join(device_path, "autoexec.be"), "wb") as f:
                    f.write(berry_script.encode("utf-8"))

                device_script = generate_download_berry_script(frontend_url, device)
                send_mqtt_message_to_tasmota(device, "Br", device_script)

            return HttpResponse(status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Unexpected error during IoT deployment")
            return HttpResponse("Internal server error.", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IoTDeviceID(generics.RetrieveUpdateDestroyAPIView):
    """View to get the information, update and delete a unique model. The model PK has be passed in the URL.

    URL: /iot-devices/{:iot-device-pk}
    """

    queryset = IoTDevice.objects.all()
    serializer_class = IoTDeviceSerializer


class IoTDeviceRetrieveModelView(generics.RetrieveAPIView):
    """
    View to expose the model file given a token.

    URL: GET /iot-devices/model/{token}
    """

    def get(self, request, token, format=None):
        device = get_object_or_404(IoTDevice, token=token)
        model_path = os.path.join(settings.DEVICES_ROOT, device.token, "model.tflite")

        response = FileResponse(
            open(model_path, "rb"), content_type="application/octet-stream"
        )
        response["Content-Disposition"] = "attachment; filename*=UTF-8''model.tflite"
        return response


class IoTDeviceRetrieveScriptView(generics.RetrieveAPIView):
    """
    View to expose the berry script file given a token.

    URL: GET /iot-devices/script/{token}
    """

    def get(self, request, token, format=None):
        device = get_object_or_404(IoTDevice, token=token)
        script_path = os.path.join(settings.DEVICES_ROOT, device.token, "autoexec.be")

        response = FileResponse(
            open(script_path, "rb"), content_type="application/octet-stream"
        )
        response["Content-Disposition"] = "attachment; filename*=UTF-8''autoexec.be"
        return response
