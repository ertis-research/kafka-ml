import json
import logging
import copy
import traceback

from django.http import HttpResponse
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client

from automl.serializers import DatasourceSerializer

from automl.models import Deployment, Datasource

from confluent_kafka import Producer

from automl.utils import kubernetes_config


def delete_deploy(inference_id, token=None, external_host=None):
    """Delete a previous deployment.
    You can also provide an external host and its token
    to delete a deployment there. If one of them is not provided,
    this function will try to delete the deployment locally.

    Parameters:
        dict: inference_id ; Deployment ID
        str: token
        str: external_host (e.g. "https://192.168.65.3:6443")

    Return:
        Response of Kubernetes Cluster
    """
    api_client = kubernetes_config(token=token, external_host=external_host)
    api_instance = client.CoreV1Api(api_client)
    api_response = api_instance.delete_namespaced_replication_controller(
        name="model-inference-" + str(inference_id),
        namespace=settings.KUBE_NAMESPACE,
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )
    return api_response


class DatasourceList(generics.ListCreateAPIView):
    """View to get the list of datasources and create a new datasource

    URL: /datasources
    """

    queryset = Datasource.objects.all()
    serializer_class = DatasourceSerializer

    """View to create a new datasource and send it to kafka
        
        URL: /datasources/kafka
    """

    def post(self, request, format=None):
        """Expects a JSON in the request body with the information to create a new datasource

        Args JSON:
            topic (str): Kafka topic where the data has been sent
            input_format (str): Input format of the data
            data_type (str): Type of the data
            label_type (str): Type of the label
            data_reshape (str): Reshape of the data. Optional
            label_reshape (str): Reshape of the label. Optional
            validation_rate (float): Validation rate.
            test_rate (float): Test rate.
            total_msg (int): Total messages sent
            description (str): Description of the dataset
            time (str): Timemestamp when the dataset was sent
            deployment (str): Deployment ID for the data

            Example:
            {
                'topic': 'automl:0:70000'
                'input_format': 'RAW',
                'data_type' : 'uint8',
                'label_type': 'uint8'
                'data_reshape' : '28 28',
                'label_reshape' : '',
                'validation_rate' : 0.1,
                'test_rate' : 0.1,
                'total_msg': 70000
                'description': 'Mnist dataset',
                'time': '2020-04-03T00:00:00Z',
                'deployment': '2',
            }
        Returns:
            HTTP_201_CREATED: if the datasource has been sent correctly to Kafka and created
            HTTP_400_BAD_REQUEST: if there has been any error: kafka, saving, etc.
        """
        try:
            data = json.loads(request.body)
            serializer = DatasourceSerializer(data=data)
            deployment_id = int(data["deployment"])
            if (
                serializer.is_valid()
                and Deployment.objects.filter(pk=deployment_id).exists()
            ):
                """Checks if data received is valid and deployment received exists in the system"""

                conf = {"bootstrap.servers": settings.BOOTSTRAP_SERVERS}
                producer = Producer(conf)
                """Creates a Kafka Producer to send the message to the control topic"""

                kafka_data = copy.deepcopy(data)
                del kafka_data["deployment"]
                del kafka_data["time"]
                """Deletes unused attributes"""

                kafka_data["input_config"] = json.loads(kafka_data["input_config"])

                key = bytes([deployment_id])
                data_bytes = json.dumps(kafka_data).encode("utf-8")

                logging.info(
                    "Control message to be sent to kafka control topic %s", kafka_data
                )

                producer.produce(settings.CONTROL_TOPIC, key=key, value=data_bytes)
                """Sends the data to Kafka"""
                producer.flush()
                """Waits until data is sent"""

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse(
                "Deployment not valid", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class DatasourceToKafka(generics.CreateAPIView):
    """View to create a new datasource and send it to kafka

    URL: /datasources/kafka
    """

    def post(self, request, format=None):
        """Expects a JSON in the request body with the information to create a new datasource

        Args JSON:
            topic (str): Kafka topic where the data has been sent
            input_format (str): Input format of the data
            data_type (str): Type of the data
            label_type (str): Type of the label
            data_reshape (str): Reshape of the data. Optional
            label_reshape (str): Reshape of the label. Optional
            validation_rate (float): Validation rate.
            test_rate (float): Test rate.
            total_msg (int): Total messages sent
            description (str): Description of the dataset
            time (str): Timemestamp when the dataset was sent
            deployment (str): Deployment ID for the data

            Example:
            {
                'topic': 'automl:0:70000'
                'input_format': 'RAW',
                'data_type' : 'uint8',
                'label_type': 'uint8'
                'data_reshape' : '28 28',
                'label_reshape' : '',
                'validation_rate' : 0.1,
                'test_rate' : 0.1,
                'total_msg': 70000
                'description': 'Mnist dataset',
                'time': '2020-04-03T00:00:00Z',
                'deployment': '2',
            }
        Returns:
            HTTP_201_CREATED: if the datasource has been sent correctly to Kafka and created
            HTTP_400_BAD_REQUEST: if there has been any error: kafka, saving, etc.
        """
        try:
            data = json.loads(request.body)
            serializer = DatasourceSerializer(data=data)
            deployment_id = int(data["deployment"])
            if (
                serializer.is_valid()
                and Deployment.objects.filter(pk=deployment_id).exists()
            ):
                """Checks if data received is valid and deployment received exists in the system"""

                conf = {"bootstrap.servers": settings.BOOTSTRAP_SERVERS}
                producer = Producer(conf)
                """Creates a Kafka Producer to send the message to the control topic"""

                kafka_data = copy.deepcopy(data)
                del kafka_data["deployment"]
                del kafka_data["time"]
                """Deletes unused attributes"""

                kafka_data["input_config"] = json.loads(kafka_data["input_config"])

                key = bytes([deployment_id])
                data_bytes = json.dumps(kafka_data).encode("utf-8")

                logging.info(
                    "Control message to be sent to kafka control topic %s", kafka_data
                )

                producer.produce(settings.CONTROL_TOPIC, key=key, value=data_bytes)
                """Sends the data to Kafka"""
                producer.flush()
                """Waits until data is sent"""

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse(
                "Deployment not valid", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
