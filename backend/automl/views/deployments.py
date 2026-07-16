import json
from django.http import JsonResponse
import os
import sys
import logging
import copy
import traceback
import requests
import re
import random
import string

from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import (
    ConfigurationSerializer,
    DeploymentSerializer,
    DatasourceSerializer,
)
from automl.serializers import (
    TrainingResultSerializer,
    SimpleResultSerializer,
    DeployDeploymentSerializer,
    DeployInferenceSerializer,
)
from automl.serializers import InferenceSerializer, SimplerResultSerializer

from automl.models import (
    MLModel,
    Deployment,
    Configuration,
    TrainingResult,
    Datasource,
    Inference,
)

from confluent_kafka import Producer

from automl.utils import is_blank, kubernetes_config, parse_kwargs_fit

from automl.views.utils import job_manifest_generator

class DeploymentList(generics.ListCreateAPIView):
    """View to get the list of deployments and create a new deployment in Kubernetes

    URL: /deployments
    """

    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer

    def post(self, request, format=None):
        """Expects a JSON in the request body with the information to create a new deployment

        Args JSON:
            batch (int): Name of the model
            kwargs_fit (str): Arguments required for training the models
            configuration (int): PK of the Configuration associated with the deployment

            Example:
            {
                "batch":"10,
                "kwargs_fit":"epochs=5, steps_per_epoch=1000",
                "configuration": 1
            }
        Returns:
            HTTP_201_CREATED: if the deployment has been created correctly and deployed in Kubernetes
            HTTP_400_BAD_REQUEST: if there has been any error.
        """
        try:
            data = json.loads(request.body)

            # GPU Memory allocation
            gpu_mem_to_allocate = data["gpumem"]
            data.pop("gpumem")

            # tf_kwargs verification
            tf_kwargs_fit_empty, tf_kwargs_val_empty = False, False
            if data["tf_kwargs_fit"] != "":
                tf_kwargs_fit_empty = False
                if data["tf_kwargs_val"] == "":
                    tf_kwargs_val_empty = True
                    data.pop("tf_kwargs_val")
            else:
                data.pop("tf_kwargs_fit")
                data.pop("tf_kwargs_val")
                tf_kwargs_fit_empty, tf_kwargs_val_empty = True, True

            # pth_kwargs verification
            pth_kwargs_fit_empty, pth_kwargs_val_empty = False, False
            if data["pth_kwargs_fit"] != "":
                pth_kwargs_fit_empty = False
                if data["pth_kwargs_val"] == "":
                    pth_kwargs_val_empty = True
                    data.pop("pth_kwargs_val")
            else:
                data.pop("pth_kwargs_fit")
                data.pop("pth_kwargs_val")
                pth_kwargs_fit_empty, pth_kwargs_val_empty = True, True

            serializer = DeployDeploymentSerializer(data=data)
            if serializer.is_valid():
                try:
                    """KUBERNETES code goes here"""
                    config.load_incluster_config()  # To run inside the container
                    # config.load_kube_config() # To run externally
                    logging.info(
                        "Connection to Kubernetes %s %s",
                        os.environ.get("KUBE_TOKEN"),
                        os.environ.get("KUBE_HOST"),
                    )
                    api_client = kubernetes_config(
                        token=os.environ.get("KUBE_TOKEN"),
                        external_host=os.environ.get("KUBE_HOST"),
                    )
                    api_instance = client.BatchV1Api(api_client)
                    # api_instance = client.BatchV1Api()

                    if not tf_kwargs_fit_empty:
                        # TensorFlow Verification
                        tf_kwargs_fit = parse_kwargs_fit(data["tf_kwargs_fit"])
                        tf_kwargs_val = (
                            parse_kwargs_fit(data["tf_kwargs_val"])
                            if not tf_kwargs_val_empty
                            else json.dumps({})
                        )

                        data_to_send = {
                            "batch": data["batch"],
                            "kwargs_fit": tf_kwargs_fit,
                            "kwargs_val": tf_kwargs_val,
                        }
                        tf_resp = requests.post(
                            settings.TENSORFLOW_EXECUTOR_URL + "check_deploy_config/",
                            data=json.dumps(data_to_send),
                        )
                        if tf_resp.status_code != 200:
                            raise ValueError("Some TensorFlow arguments are not valid.")

                        if (
                            data.get("incremental", False) is True
                            and data.get("indefinite", False) is True
                            and Configuration.objects.filter(
                                pk=data["configuration"]
                            ).exists()
                        ):
                            obj = Configuration.objects.get(pk=data["configuration"])

                            for m in obj.ml_models.all():
                                if not m.distributed:
                                    if data["monitoring_metric"] not in m.code:
                                        raise ValueError(
                                            "Monitoring metric does not match."
                                        )

                    if not pth_kwargs_fit_empty:
                        # PyTorch Verification
                        pth_kwargs_fit = parse_kwargs_fit(data["pth_kwargs_fit"])
                        pth_kwargs_val = (
                            parse_kwargs_fit(data["pth_kwargs_val"])
                            if not pth_kwargs_val_empty
                            else json.dumps({})
                        )

                        data_to_send = {
                            "batch": data["batch"],
                            "kwargs_fit": pth_kwargs_fit,
                            "kwargs_val": pth_kwargs_val,
                        }
                        pth_resp = requests.post(
                            settings.PYTORCH_EXECUTOR_URL + "check_deploy_config/",
                            data=json.dumps(data_to_send),
                        )
                        if pth_resp.status_code != 200:
                            raise ValueError("Some PyTorch arguments are not valid.")

                    deployment = serializer.save()

                    for result in TrainingResult.objects.filter(deployment=deployment):
                        if result.model.framework == "tf":
                            image = settings.TENSORFLOW_TRAINING_MODEL_IMAGE
                            kwargs_fit = tf_kwargs_fit
                            kwargs_val = tf_kwargs_val
                        elif result.model.framework == "pth":
                            image = settings.PYTORCH_TRAINING_MODEL_IMAGE
                            kwargs_fit = pth_kwargs_fit
                            kwargs_val = pth_kwargs_val

                        if not result.model.distributed:
                            if not deployment.incremental:
                                if not deployment.federated:
                                    job_manifest = job_manifest_generator.single_classic_training(
                                        result,
                                        deployment,
                                        image,
                                        1,          # Case 1: Single Classic Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                                else:                                    
                                    job_manifest = job_manifest_generator.single_federated_training(
                                        result,
                                        deployment,
                                        image,
                                        5 if not deployment.blockchain else 9,
                                        # Case 5: Single Federated Training or Case 9: Single Federated Blockchain Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                            else:
                                if not deployment.federated:                                    
                                    job_manifest = job_manifest_generator.single_incremental_training(
                                        result,
                                        deployment,
                                        image,
                                        2, # Case 2: Single Incremental Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                                else:
                                    job_manifest = job_manifest_generator.single_federated_incremental_training(
                                        result,
                                        deployment,
                                        image,
                                        6, # Case 6: Single Federated Incremental Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                        elif result.model.distributed and result.model.father == None:
                            """Obtains all the distributed models from a deployment and creates a job for each group of them"""
                            result_urls = []
                            result_ids = []
                            s = str(os.environ.get("BACKEND_URL")) + "/results/"
                            n = ""

                            result_urls.append(s + str(result.id))
                            result_ids.append(str(result.id))
                            n += "-" + str(result.id)
                            current = result

                            while hasattr(current.model, "child"):
                                current = TrainingResult.objects.get(
                                    model=current.model.child, deployment=deployment
                                )
                                result_urls.append(s + str(current.id))
                                result_ids.append(str(current.id))
                                n += "-" + str(current.id)

                            result_urls.reverse()
                            result_ids.reverse()

                            if not deployment.incremental:
                                if not deployment.federated:
                                    job_manifest = job_manifest_generator.distributed_classic_training(
                                        n,
                                        result_urls,
                                        result_ids,
                                        deployment,
                                        image,
                                        3, # Case 3: Distributed Classic Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings)
                                else:
                                    job_manifest = job_manifest_generator.distributed_federated_training(
                                        n,
                                        result_urls,
                                        result_ids,
                                        deployment,
                                        image,
                                        7,  # Case 7: Federated Distributed Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                            else:
                                if not deployment.federated:
                                    job_manifest = job_manifest_generator.distributed_incremental_training(
                                        n,
                                        result_urls,
                                        result_ids,
                                        deployment,
                                        image,
                                        4,  # Case 4: Distributed Incremental Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )
                                else:
                                    job_manifest = job_manifest_generator.distributed_federated_incremental_training(
                                        n,
                                        result_urls,
                                        result_ids,
                                        deployment,
                                        image,
                                        8,  # Case 8: Federated Distributed Incremental Training
                                        kwargs_fit,
                                        kwargs_val,
                                        settings,
                                    )

                        if gpu_mem_to_allocate > 0:
                            job_manifest["spec"]["template"]["spec"]["containers"][0][
                                "resources"
                            ] = {"limits": {"nvidia.com/gpu": gpu_mem_to_allocate}}
                            job_manifest["spec"]["template"]["spec"]["containers"][0][
                                "env"
                            ].append({"name": "NVIDIA_VISIBLE_DEVICES", "value": "all"})
                            job_manifest["spec"]["template"]["spec"][
                                "runtimeClassName"
                            ] = "nvidia"

                        resp = api_instance.create_namespaced_job(
                            body=job_manifest, namespace=settings.KUBE_NAMESPACE
                        )
                        logging.info("Job created. status='%s'" % str(resp.status))

                    return HttpResponse(status=status.HTTP_201_CREATED)
                except ValueError as ve:
                    traceback.print_exc()
                    logging.error(str(ve))
                    return HttpResponse(str(ve), status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    traceback.print_exc()
                    Deployment.objects.filter(pk=deployment.pk).delete()
                    logging.error(str(e))
                    return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class DeploymentsConfigurationID(generics.RetrieveDestroyAPIView):
    """View to get the list of deployments of a configuration and delete an deployment. The configuration PK has be passed in the URL.


    URL: GET /deployments/{:configuration_pk}
    URL: DELETE /deployments/{:configuration_pk}
    """

    def get(self, request, pk, format=None):
        """Gets the list of deployments of a configuration"""

        if Configuration.objects.filter(pk=pk).exists():
            configuration = Configuration.objects.get(pk=pk)
            deployments = Deployment.objects.filter(configuration=configuration)
            serializer = DeploymentSerializer(deployments, many=True)
            return HttpResponse(json.dumps(serializer.data), status=status.HTTP_200_OK)
        else:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Deletes a deployment"""
        try:
            if Deployment.objects.filter(pk=pk).exists():
                obj = Deployment.objects.get(pk=pk)
                if TrainingResult.objects.filter(deployment=obj).exists():
                    return HttpResponse(
                        "Deployment cannot be deleted. Please delete its training results first.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse(
                "Deployment does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class DeploymentResultID(generics.RetrieveDestroyAPIView):
    """View to get the list of results of a deployment.

    URL: GET /deployments/results/{:id_deployment} to get the list of results of a deployment
    """

    def get(self, request, pk, format=None):
        """Gets the list of deployments of a configuration"""

        if Deployment.objects.filter(pk=pk).exists():
            deployment = Deployment.objects.get(pk=pk)
            results = TrainingResult.objects.filter(deployment=deployment)
            serializer = TrainingResultSerializer(results, many=True)
            return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)
        else:
            return HttpResponse(
                "Deployment not found", status=status.HTTP_400_BAD_REQUEST
            )
