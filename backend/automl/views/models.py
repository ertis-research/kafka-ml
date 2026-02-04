import json
import os
import logging
import copy
import traceback
import requests
import re

from django.http import HttpResponse
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import MLModelSerializer, DatasourceSerializer
from automl.serializers import DeployInferenceSerializer

from automl.models import (
    MLModel,
    Deployment,
    Configuration,
    TrainingResult,
    Datasource,
    Inference,
)

from confluent_kafka import Producer

from automl.utils import kubernetes_config, is_blank


class ModelList(generics.ListCreateAPIView):
    """View to get the list of models and create a new model

    URL: /models
    """

    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer

    def post(self, request, format=None):
        """Expects a JSON in the request body with the information to create a new model.

        Args JSON:
            name (str): Name of the model
            imports (str): Imports required to compile the model
            code (str): Code (formatted) of the model to be compiled

            Example:
            {
                "name":"ML model",
                "imports":"import tensorflow as ta",
                "code":"model = ta.keras.Sequential([\n
                    ta.keras.layers.Flatten(input_shape=(28, 28)),\n
                    ta.keras.layers.Dense(128, activation=tf.nn.relu),\n
                    ta.keras.layers.Dense(10, activation=tf.nn.softmax)\n])
                    \nmodel.compile(optimizer='adam',\n
                    loss='sparse_categorical_crossentropy',\n
                    metrics=['accuracy'])"
            }
        Returns:
            HTTP_201_CREATED: if the model has been created correctly
            HTTP_400_BAD_REQUEST: if there has been any error: code not valid, saving the model, etc.
        """
        try:
            data = json.loads(request.body)
            logging.info("Data code received %s", data["code"])

            imports_code = "" if "imports" not in data else data["imports"]

            if "distributed" in data:
                data_to_send = {
                    "imports_code": imports_code,
                    "model_code": data["code"],
                    "distributed": data["distributed"],
                    "request_type": "check",
                }
            else:
                data_to_send = {
                    "imports_code": imports_code,
                    "model_code": data["code"],
                    "distributed": False,
                    "request_type": "check",
                }

            if data["framework"] == "pth":
                resp = requests.post(
                    settings.PYTORCH_EXECUTOR_URL + "exec_pth/",
                    data=json.dumps(data_to_send),
                )
            else:
                resp = requests.post(
                    settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/",
                    data=json.dumps(data_to_send),
                )

            """Prints the information of the model"""
            if resp.status_code == 200:
                serializer = MLModelSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class DistributedModelList(generics.ListAPIView):
    """View to get the list of distributed models

    URL: /models/distributed
    """

    queryset = MLModel.objects.filter(distributed=True)
    serializer_class = MLModelSerializer


class FatherModelList(generics.ListAPIView):
    """View to get the list of models which have no father

    URL: /models/fathers
    """

    queryset = MLModel.objects.filter(father=None)
    serializer_class = MLModelSerializer


class ModelID(generics.RetrieveUpdateDestroyAPIView):
    """View to get the information, update and delete a unique model. The model PK has be passed in the URL.

    URL: /models/{:model_pk}
    """

    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer

    def put(self, request, pk, format=None):
        """Updates the model corresponding with PK received
        Args:
            pk (int): Primary key of the model (in the URL)

        Returns:
            HTTP_200_OK: if the model has been removed
            HTTP_400_BAD_REQUEST: if there has been any error deleting the model.
        """
        try:
            if MLModel.objects.filter(pk=pk).exists():
                data = json.loads(request.body)
                model_obj = MLModel.objects.get(pk=pk)
                serializer = MLModelSerializer(model_obj, data=data)
                if serializer.is_valid():
                    if (
                        data["code"] != model_obj.code
                        or data["framework"] != model_obj.framework
                    ):
                        imports_code = "" if "imports" not in data else data["imports"]

                        if "distributed" in data:
                            data_to_send = {
                                "imports_code": imports_code,
                                "model_code": data["code"],
                                "distributed": data["distributed"],
                                "request_type": "check",
                            }
                        else:
                            data_to_send = {
                                "imports_code": imports_code,
                                "model_code": data["code"],
                                "distributed": False,
                                "request_type": "check",
                            }

                        if data["framework"] == "pth":
                            resp = requests.post(
                                settings.PYTORCH_EXECUTOR_URL + "exec_pth/",
                                data=json.dumps(data_to_send),
                            )
                        else:
                            resp = requests.post(
                                settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/",
                                data=json.dumps(data_to_send),
                            )

                        """Prints the information of the model"""
                        if resp.status_code != 200:
                            return HttpResponse(
                                "Model not valid.", status=status.HTTP_400_BAD_REQUEST
                            )
                    serializer.save()
                    return HttpResponse(status=status.HTTP_200_OK)
                else:
                    return HttpResponse(
                        "Information not valid", status=status.HTTP_400_BAD_REQUEST
                    )
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request, pk, format=None):
        """Deletes a model"""
        try:
            if MLModel.objects.filter(pk=pk).exists():
                model_obj = MLModel.objects.get(pk=pk)
                if Configuration.objects.filter(ml_models=model_obj).exists():
                    return HttpResponse(
                        "Model cannot be deleted since it is used in a configuration. Consider to delete the configuration.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                model_obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse(
                "Model does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class ModelResultID(generics.RetrieveAPIView):
    """View to get a model from its result ID

    URL: /models/result/{:id_result}
    """

    def get(self, request, pk, format=None):
        if TrainingResult.objects.filter(pk=pk).exists():
            result = TrainingResult.objects.get(pk=pk)
            model = result.model
            serializer = MLModelSerializer(model, many=False)
            return HttpResponse(json.dumps(serializer.data), status=status.HTTP_200_OK)
        else:
            return HttpResponse(
                "TrainingResult not found", status=status.HTTP_400_BAD_REQUEST
            )

    """View to get information and deploy a new inference from a training result
        
        URL: /results/inference/{:id_result}
    """

    def get(self, request, pk, format=None):
        """Checks if the training result exists and returns the input format and configuration if there any in other inference or
        datasource objects to facilitate the inference deployment.
        """
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                response = {
                    "input_format": "",
                    "input_config": "",
                }
                result = TrainingResult.objects.get(id=pk)
                inferences = Inference.objects.filter(model_result=result)
                if inferences.count() > 0:
                    response["input_format"] = inferences[0].input_format
                    response["input_config"] = inferences[0].input_config
                else:
                    model = result.model
                    datasources = Datasource.objects.filter(
                        deployment=str(result.deployment.id)
                    )

                    if datasources.count() > 0:
                        response["input_format"] = datasources[0].input_format
                        input_config = datasources[0].input_config

                        if not hasattr(model, "child"):
                            response["input_config"] = (
                                input_config  # TODO change to input_config
                            )
                        else:
                            data_to_send = {
                                "imports_code": model.imports,
                                "model_code": model.code,
                                "distributed": model.distributed,
                                "request_type": "input_shape",
                            }
                            resp = requests.post(
                                settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/",
                                data=json.dumps(data_to_send),
                            )

                            input_shape = resp.content.decode("utf-8")

                            sub = re.search(", (.+?)\)", input_shape)

                            if sub:
                                shape = sub.group(1)

                                dictionary = json.loads(input_config)

                                dictionary["data_reshape"] = shape.replace(",", "")

                                new_input_config = json.dumps(dictionary)

                                response["input_config"] = new_input_config
                            else:
                                response["input_config"] = input_config

                            if new_input_config is None:
                                dic = json.loads(input_config)
                            else:
                                dic = json.loads(new_input_config)

                            dic["data_type"] = "float32"
                            aux_input_config = json.dumps(dic)
                            response["input_config"] = aux_input_config
                return HttpResponse(json.dumps(response), status=status.HTTP_200_OK)
        except Exception:
            traceback.print_exc()
            return HttpResponse("Result not found", status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, pk, format=None):
        """Expects a JSON in the request body with the information to deploy a inference.
        The result PK has to be in the URL.

        Args:
            pk (int): Primary key of the result (in the URL)
            replicas (int): number of replicas to be deployed
            input_format (str): input format of the data received
            configuration (str): configuration input format for the inference
            input_topic: topic to receive the data
            output_topic: topic to send output data
            upper_topic: topic to send the data to the upper layer
                Example:
                    {
                        "replicas": 2,
                        "input_format": "RAW",
                        "configuration": {
                            "data_type": "uint8",
                            "label_type": "uint8",
                            "data_reshape": "28 28",
                            "label_reshape": ""
                        }
                        "input_topic": "inference-input",
                        "output_topic": "inference-output",
                        "upper_topic": "inference-upper"
                    }

        Returns:
            HTTP_200_OK: if the inference has been deployed
            HTTP_400_BAD_REQUEST: if there has been any error deploying the inference
        """
        if TrainingResult.objects.filter(pk=pk).exists():
            try:
                data = json.loads(request.body)
                gpu_mem_to_allocate = data["gpumem"]
                data.pop("gpumem")
                result = TrainingResult.objects.get(id=pk)
                serializer = DeployInferenceSerializer(data=data)

                if serializer.is_valid() and result.status == "finished":
                    inference = serializer.save()
                    try:
                        config.load_incluster_config()  # To run inside the container
                        # config.load_kube_config() # To run externally
                        # api_instance = client.CoreV1Api()

                        if not is_blank(inference.external_host) and not is_blank(
                            inference.token
                        ):
                            token = inference.token
                            external_host = inference.external_host
                        else:
                            token = os.environ.get("KUBE_TOKEN")
                            external_host = os.environ.get("KUBE_HOST")

                        api_client = kubernetes_config(
                            token=token, external_host=external_host
                        )
                        api_instance = client.CoreV1Api(api_client)

                        if not is_blank(inference.input_kafka_broker):
                            input_kafka_broker = inference.input_kafka_broker
                        else:
                            input_kafka_broker = settings.BOOTSTRAP_SERVERS

                        if not is_blank(inference.output_kafka_broker):
                            output_kafka_broker = inference.output_kafka_broker
                        else:
                            output_kafka_broker = settings.BOOTSTRAP_SERVERS

                        logging.info("Inference deployed in host [%s]", external_host)
                        logging.info(
                            "Input kafka broker is [%s] and output kafka broker is [%s]",
                            input_kafka_broker,
                            output_kafka_broker,
                        )

                        if result.model.framework == "tf":
                            image = settings.TENSORFLOW_INFERENCE_MODEL_IMAGE
                        elif result.model.framework == "pth":
                            image = settings.PYTORCH_INFERENCE_MODEL_IMAGE

                        if not result.model.distributed:
                            manifest = {
                                "apiVersion": "v1",
                                "kind": "ReplicationController",
                                "metadata": {
                                    "name": "model-inference-" + str(inference.id),
                                    "labels": {
                                        "name": "model-inference-" + str(inference.id)
                                    },
                                },
                                "spec": {
                                    "replicas": inference.replicas,
                                    "selector": {
                                        # 'matchLabels': {
                                        "app": "inference" + str(inference.id)
                                        # }
                                    },
                                    "template": {
                                        "metadata": {
                                            "labels": {
                                                "app": "inference" + str(inference.id)
                                            }
                                        },
                                        "spec": {
                                            "containers": [
                                                {
                                                    "image": image,
                                                    "name": "inference",
                                                    "env": [
                                                        {
                                                            "name": "INPUT_BOOTSTRAP_SERVERS",
                                                            "value": input_kafka_broker,
                                                        },
                                                        {
                                                            "name": "OUTPUT_BOOTSTRAP_SERVERS",
                                                            "value": output_kafka_broker,
                                                        },
                                                        {
                                                            "name": "MODEL_ARCH_URL",
                                                            "value": str(
                                                                os.environ.get(
                                                                    "BACKEND_URL"
                                                                )
                                                            )
                                                            + "/results/"
                                                            + str(result.id),
                                                        },
                                                        {
                                                            "name": "MODEL_URL",
                                                            "value": str(
                                                                os.environ.get(
                                                                    "BACKEND_URL"
                                                                )
                                                            )
                                                            + "/results/model/"
                                                            + str(result.id),
                                                        },
                                                        {
                                                            "name": "INPUT_FORMAT",
                                                            "value": inference.input_format,
                                                        },
                                                        {
                                                            "name": "INPUT_CONFIG",
                                                            "value": inference.input_config,
                                                        },
                                                        {
                                                            "name": "INPUT_TOPIC",
                                                            "value": inference.input_topic,
                                                        },
                                                        {
                                                            "name": "OUTPUT_TOPIC",
                                                            "value": inference.output_topic,
                                                        },
                                                        {
                                                            "name": "GROUP_ID",
                                                            "value": "inf"
                                                            + str(result.id),
                                                        },
                                                    ],
                                                }
                                            ],
                                            "imagePullPolicy": "Always",
                                        },
                                    },
                                },
                            }
                        else:
                            if not is_blank(inference.upper_kafka_broker):
                                upper_kafka_broker = inference.upper_kafka_broker
                            else:
                                upper_kafka_broker = settings.BOOTSTRAP_SERVERS

                            manifest = {
                                "apiVersion": "v1",
                                "kind": "ReplicationController",
                                "metadata": {
                                    "name": "model-inference-" + str(inference.id),
                                    "labels": {
                                        "name": "model-inference-" + str(inference.id)
                                    },
                                },
                                "spec": {
                                    "replicas": inference.replicas,
                                    "selector": {
                                        # 'matchLabels': {
                                        "app": "inference" + str(inference.id)
                                        # }
                                    },
                                    "template": {
                                        "metadata": {
                                            "labels": {
                                                "app": "inference" + str(inference.id)
                                            }
                                        },
                                        "spec": {
                                            "containers": [
                                                {
                                                    "image": settings.TENSORFLOW_INFERENCE_MODEL_IMAGE,
                                                    "name": "inference",
                                                    "env": [
                                                        {
                                                            "name": "INPUT_BOOTSTRAP_SERVERS",
                                                            "value": input_kafka_broker,
                                                        },
                                                        {
                                                            "name": "OUTPUT_BOOTSTRAP_SERVERS",
                                                            "value": output_kafka_broker,
                                                        },
                                                        {
                                                            "name": "UPPER_BOOTSTRAP_SERVERS",
                                                            "value": upper_kafka_broker,
                                                        },
                                                        {
                                                            "name": "MODEL_URL",
                                                            "value": str(
                                                                os.environ.get(
                                                                    "BACKEND_URL"
                                                                )
                                                            )
                                                            + "/results/model/"
                                                            + str(result.id),
                                                        },
                                                        {
                                                            "name": "INPUT_FORMAT",
                                                            "value": inference.input_format,
                                                        },
                                                        {
                                                            "name": "INPUT_CONFIG",
                                                            "value": inference.input_config,
                                                        },
                                                        {
                                                            "name": "INPUT_TOPIC",
                                                            "value": inference.input_topic,
                                                        },
                                                        {
                                                            "name": "OUTPUT_TOPIC",
                                                            "value": inference.output_topic,
                                                        },
                                                        {
                                                            "name": "OUTPUT_UPPER",
                                                            "value": inference.output_upper,
                                                        },
                                                        {
                                                            "name": "GROUP_ID",
                                                            "value": "inf"
                                                            + str(result.id),
                                                        },
                                                        {
                                                            "name": "LIMIT",
                                                            "value": str(
                                                                inference.limit
                                                            ),
                                                        },
                                                    ],
                                                }
                                            ],
                                            "imagePullPolicy": "Always",
                                        },
                                    },
                                },
                            }
                        inference.save()

                        if gpu_mem_to_allocate > 0:
                            manifest["spec"]["template"]["spec"]["containers"][0][
                                "resources"
                            ]["limits"]["nvidia.com/gpu"] = gpu_mem_to_allocate
                            manifest["spec"]["template"]["spec"]["containers"][0][
                                "env"
                            ].append({"name": "NVIDIA_VISIBLE_DEVICES", "value": "all"})
                            manifest["spec"]["template"]["spec"]["runtimeClassName"] = (
                                "nvidia"
                            )

                        api_instance.create_namespaced_replication_controller(
                            body=manifest, namespace=settings.KUBE_NAMESPACE
                        )  # create_namespaced_deployment
                        return HttpResponse(status=status.HTTP_200_OK)
                    except Exception as e:
                        Inference.objects.filter(pk=inference.pk).delete()
                        return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
                return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                traceback.print_exc()
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse("Result not found", status=status.HTTP_400_BAD_REQUEST)

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
