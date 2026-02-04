import json
import os
import logging
import traceback
import requests

from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import (
    TrainingResultSerializer,
    SimpleResultSerializer,
    SimplerResultSerializer    
)
from automl.models import (
    TrainingResult
)

from automl.utils import kubernetes_config


class TrainingResultList(generics.ListAPIView):
    """View to get the list of results

    URL: /results
    """

    queryset = TrainingResult.objects.all()
    serializer_class = TrainingResultSerializer


class TrainingResultID(generics.RetrieveUpdateDestroyAPIView):
    """View to get and upload the information of a results.

    URL: GET /results/{:id_result} to get the model file for training.
    URL: POST /results/{:id_result} to upload the information of a result.
    URL: DELETE /results/{:id_result} to delete a result.
    """

    def get(self, request, pk, format=None):
        """Gets the model file for training"""

        try:
            result = TrainingResult.objects.get(pk=pk)
            """Obtains the model filename"""

            if result.model.framework == "tf":
                data_to_send = {
                    "imports_code": result.model.imports,
                    "model_code": result.model.code,
                    "distributed": result.model.distributed,
                    "request_type": "load_model",
                }
                resp = requests.post(
                    settings.TENSORFLOW_EXECUTOR_URL + "exec_tf/",
                    data=json.dumps(data_to_send),
                )
                """Saves the model temporally"""

                response = HttpResponse(resp.content, content_type="application/model")
                response["Content-Disposition"] = 'attachment; filename="model.h5"'
            elif result.model.framework == "pth":
                response = HttpResponse(result.model.code)

            if result.status != TrainingResult.STATUS.finished:
                result.status = TrainingResult.STATUS.deployed
                result.save()

            return response
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, pk, format=None):
        """Expects a JSON in the request body with the information to upload the information of a result.
        The result PK has to be in the URL.

        Args:
            pk (int): Primary key of the result (in the URL)
            trained_model (File): file with the trained model (body)
            confussion_matrix (File): file with the confussion matrix (body)
            json (str): Information to update the result (in the body).
                train_loss_hist (str): List of trained losses
                train_acc_hist (str): List of trained accuracies
                val_loss (str): Loss in validation
                val_acc (str): Accuracy in validation

                Request example:
                    FILES: trained_model: '...'
                           confussion_matrix: '...'
                    Body:
                    {
                        'train_loss_hist': '0.12, 0.01',
                        'train_acc_hist':  '0.92, 0.95',
                        'val_loss': 0.12,
                        'val_acc': 0.95,
                    }
        Returns:
            HTTP_200_OK: if the result has been updated
            HTTP_400_BAD_REQUEST: if there has been any error updating the result
        """
        if (
            request.FILES["trained_model"]
            and TrainingResult.objects.filter(pk=pk).exists()
        ):
            try:
                data = json.loads(request.data["data"])
                obj = TrainingResult.objects.get(id=pk)

                if data.get("indefinite", False):
                    deployment = obj.deployment
                    model = obj.model
                    obj = TrainingResult.objects.create(
                        deployment=deployment, model=model
                    )

                    data.pop("indefinite")

                serializer = SimpleResultSerializer(obj, data=data, partial=True)

                if serializer.is_valid():
                    serializer.save()
                else:
                    logging.info("Cannot save training result")
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

                trained_model = request.FILES["trained_model"]
                if not obj.model.distributed:
                    confussion_matrix = (
                        request.FILES["confussion_matrix"]
                        if obj.deployment.conf_mat_settings and obj.test_metrics != {}
                        else None
                    )
                else:
                    confussion_matrix = None

                fs = FileSystemStorage()
                path = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)

                if confussion_matrix is not None:
                    if os.path.exists(path + str(obj.id) + ".png"):
                        os.remove(path + str(obj.id) + ".png")

                    fs.save(path + str(obj.id) + ".png", confussion_matrix)
                    obj.confusion_mat_img.name = (
                        settings.TRAINED_MODELS_DIR + str(obj.id) + ".png"
                    )

                if obj.model.framework == "tf":
                    if os.path.exists(path + str(obj.id) + ".h5"):
                        os.remove(path + str(obj.id) + ".h5")

                    fs.save(path + str(obj.id) + ".h5", trained_model)
                    obj.trained_model.name = (
                        settings.TRAINED_MODELS_DIR + str(obj.id) + ".h5"
                    )
                elif obj.model.framework == "pth":
                    if os.path.exists(path + str(obj.id) + ".pth"):
                        os.remove(path + str(obj.id) + ".pth")

                    fs.save(path + str(obj.id) + ".pth", trained_model)
                    obj.trained_model.name = (
                        settings.TRAINED_MODELS_DIR + str(obj.id) + ".pth"
                    )

                obj.status = TrainingResult.STATUS.finished
                obj.save()
                return HttpResponse(status=status.HTTP_200_OK)
            except Exception as e:
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse("File not found", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Deletes a training result"""
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                obj = TrainingResult.objects.get(pk=pk)
                if obj.status not in ["finished", "stopped"]:
                    return HttpResponse(
                        "Training result in use, please stop it before delete.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                filename = (
                    os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)
                    + str(obj.id)
                    + ".h5"
                )
                """Obtains the model filename"""

                if os.path.exists(filename):
                    os.remove(filename)
                """Deletes the trained model"""

                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse(
                "Result does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class TrainingResultMetricsID(generics.ListCreateAPIView):
    """View to upload the metrics of a result per epoch.

    URL: POST /results_metrics/{:id_result} to upload the metrics of a result per epoch.
    """

    def post(self, request, pk, format=None):
        """Expects a JSON in the request body with the information to upload the metrics of a result per epoch.
        The result PK has to be in the URL.

        Args:
            pk (int): Primary key of the result (in the URL)
            json (str): Information to update the result (in the body).
                train_loss (str): Loss in training
                train_acc (str): Accuracy in training
                val_loss (str): Loss in validation
                val_acc (str): Accuracy in validation

                Request example:
                    Body:
                    {
                        'train_loss': 0.12,
                        'train_acc': 0.92,
                        'val_loss': 0.12,
                        'val_acc': 0.95,
                    }
        Returns:
            HTTP_200_OK: if the result has been updated
            HTTP_400_BAD_REQUEST: if there has been any error updating the result
        """
        if TrainingResult.objects.filter(pk=pk).exists():
            try:
                data = json.loads(request.data["data"])
                obj = TrainingResult.objects.get(id=pk)
                serializer = SimplerResultSerializer(obj, data=data, partial=True)

                if serializer.is_valid():
                    serializer.save()
                else:
                    logging.info("Cannot save training result")
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

                obj.save()
                return HttpResponse(status=status.HTTP_200_OK)
            except Exception as e:
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse(
            "Training result does not exist", status=status.HTTP_400_BAD_REQUEST
        )


class TrainingResultStop(generics.CreateAPIView):
    """View to stop from Kubernetes and delete a training result

    URL: /inferences/{:id_inference}
    """

    def post(self, request, pk, format=None):
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                result = TrainingResult.objects.get(pk=pk)
                if result.status == "deployed":
                    try:
                        config.load_incluster_config()  # To run inside the container
                        # config.load_kube_config() # To run externally
                        # api_instance = client.BatchV1Api()
                        api_client = kubernetes_config(
                            token=os.environ.get("KUBE_TOKEN"),
                            external_host=os.environ.get("KUBE_HOST"),
                        )
                        api_instance = client.BatchV1Api(api_client)

                        if (
                            result.deployment.federated
                            and not result.deployment.blockchain
                        ):
                            job_name = "federated-model-training-controller-" + str(
                                result.id
                            )
                        elif (
                            result.deployment.federated and result.deployment.blockchain
                        ):
                            job_name = (
                                "federated-blockchain-model-training-controller-"
                                + str(result.id)
                            )
                        else:
                            job_name = "model-training-" + str(result.id)

                        api_response = api_instance.delete_namespaced_job(
                            name=job_name,
                            namespace=settings.KUBE_NAMESPACE,
                            body=client.V1DeleteOptions(
                                propagation_policy="Foreground", grace_period_seconds=5
                            ),
                        )
                        logging.info(
                            "Job deleted. status='%s'" % str(api_response.status)
                        )
                    except Exception as e:
                        logging.error(str(e))

                    result.status = "stopped"
                    result.save()
                    return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse(
                "Result not found or not running", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class TrainingResultGetMetrics(generics.GenericAPIView):
    """View to get training metrics from a training result

    URL: /results/chart/{:id_result}
    """

    def get(self, request, pk, format=None):
        """Get the metrics information from a training result"""
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                obj = TrainingResult.objects.get(pk=pk)

                existsValid = False
                if obj.val_metrics != {} and obj.val_metrics != []:
                    existsValid = True

                res = []

                for metric in obj.train_metrics.keys():
                    met_train = {"name": metric, "series": []}
                    if existsValid:
                        met_val = {"name": f"{metric}_val", "series": []}

                    for n_epoch in range(len(obj.train_metrics[metric])):
                        epoch_train_met = {
                            "value": obj.train_metrics[metric][n_epoch],
                            "name": n_epoch + 1,
                        }
                        met_train["series"].append(epoch_train_met)

                    if existsValid:
                        for n_epoch in range(len(obj.val_metrics[metric])):
                            epoch_valid_met = {
                                "value": obj.val_metrics[metric][n_epoch],
                                "name": n_epoch + 1,
                            }
                            met_val["series"].append(epoch_valid_met)

                    res.append(met_train)

                    if existsValid:
                        res.append(met_val)

                response = json.dumps(
                    {"metrics": res, "conf_mat": obj.confusion_matrix}
                )

                return HttpResponse(response, status=status.HTTP_200_OK)
            return HttpResponse(
                "Training result does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )


class DownloadTrainedModel(generics.RetrieveAPIView):
    """View to download a trained model

    URL: GET /results/model/{:id_result} to get the model file trained.
    """

    def get(self, request, pk, format=None):
        try:
            result = TrainingResult.objects.get(pk=pk)
            filename = os.path.join(settings.MEDIA_ROOT, result.trained_model.name)
            """Obtains the trained model filename"""

            with open(filename, "rb") as f:
                file_data = f.read()
                file_ext = None
                if result.model.framework == "tf":
                    file_ext = "h5"
                elif result.model.framework == "pth":
                    file_ext = "pth"
                response = HttpResponse(
                    file_data, content_type="application/force-download"
                )

                response["Content-Disposition"] = (
                    f'attachment; filename="model.{file_ext}"'
                )
                response["Access-Control-Expose-Headers"] = "ML-Framework"
                response["ML-Framework"] = result.model.framework

                return response

        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class DownloadConfussionMatrix(generics.RetrieveAPIView):
    """View to get the confusion matrix of a result.

    URL: GET /results/confusion_matrix/{:id_result} to get the confusion matrix of a result
    """

    def get(self, request, pk, format=None):
        try:
            result = TrainingResult.objects.get(pk=pk)
            filename = os.path.join(settings.MEDIA_ROOT, result.confusion_mat_img.name)
            """Obtains the confusion matrix filename"""

            with open(filename, "rb") as f:
                file_data = f.read()
                response = HttpResponse(file_data, content_type="application/image")

                response["Content-Disposition"] = (
                    'attachment; filename="confusion_mat.png'
                )
                return response

        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
