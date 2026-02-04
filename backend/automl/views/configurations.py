import json
import logging
import traceback

from django.http import HttpResponse

from rest_framework import status
from rest_framework import generics

from automl.serializers import (
    ConfigurationSerializer,
)

from automl.models import (
    MLModel,
    Deployment,
    Configuration
)

class ConfigurationList(generics.ListCreateAPIView):
    """View to get the list of configurations and create a new configuration

    URL: /configurations
    """

    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer

    def post(self, request, format=None):
        """Obteins all the models from a configuration"""
        try:
            data = json.loads(request.body)
            models = data["ml_models"]
            all_models = []
            for m in models:
                all_models.append(m)
                obj = MLModel.objects.get(pk=m)
                if hasattr(obj, "child"):
                    son = obj.child
                    while son:
                        all_models.append(son.id)
                        if hasattr(son, "child"):
                            son = son.child
                        else:
                            son = None
            data["ml_models"] = all_models
            serializer = ConfigurationSerializer(data=data)
            if serializer.is_valid():
                obj = serializer.save()
                return HttpResponse(status=status.HTTP_201_CREATED)
            else:
                return HttpResponse(
                    "Information not valid", status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Configuration not valid", status=status.HTTP_400_BAD_REQUEST
            )


class ConfigurationID(generics.RetrieveUpdateDestroyAPIView):
    """View to get the information, update and delete a unique configuration. The configuration PK has be passed in the URL.

    URL: /configurations/{:configuration_pk}
    """

    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer

    def put(self, request, pk, format=None):
        """Obteins all the models from a configuration"""
        try:
            if Configuration.objects.filter(pk=pk).exists():
                data = json.loads(request.body)
                models = data["ml_models"]
                all_models = []
                for m in models:
                    all_models.append(m)
                    obj = MLModel.objects.get(pk=m)
                    if hasattr(obj, "child"):
                        son = obj.child
                        while son:
                            all_models.append(son.id)
                            if hasattr(son, "child"):
                                son = son.child
                            else:
                                son = None
                data["ml_models"] = all_models
                configuration_obj = Configuration.objects.get(pk=pk)
                serializer = ConfigurationSerializer(configuration_obj, data=data)
                if serializer.is_valid():
                    serializer.save()
                    return HttpResponse(status=status.HTTP_200_OK)
                else:
                    return HttpResponse(
                        "Information not valid", status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request, pk, format=None):
        """Deletes a configuration"""
        try:
            if Configuration.objects.filter(pk=pk).exists():
                obj = Configuration.objects.get(pk=pk)
                if Deployment.objects.filter(configuration=obj).exists():
                    return HttpResponse(
                        "Configuration cannot be deleted since it is used by a deployment. Consider to delete the deployment.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse(
                "Model does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


class ConfigurationUsedFrameworks(generics.GenericAPIView):
    """View to get the frameworks used in a configuration.

    URL: /frameworksInConfiguration/{:configuration_pk}
    """

    def get(self, request, pk, format=None):
        """Get the framework used in the differents model of a configuration"""
        try:
            if Configuration.objects.filter(pk=pk).exists():
                obj = Configuration.objects.get(pk=pk)
                frameworks_used = set()

                for x in obj.ml_models.all():
                    frameworks_used.add(x.framework)

                return HttpResponse(
                    json.dumps(list(frameworks_used)), status=status.HTTP_200_OK
                )
            return HttpResponse(
                "Configuration does not exist", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )


class DistributedConfiguration(generics.GenericAPIView):
    """View to know if a configuration has distributed models.

    URL: /distributedConfiguration/{:configuration_pk}
    """

    def get(self, request, pk, format=None):
        """Return True if the configuration has distributed models else False"""
        try:
            if Configuration.objects.filter(pk=pk).exists():
                obj = Configuration.objects.get(pk=pk)
                resp = False

                for m in obj.ml_models.all():
                    if m.distributed:
                        resp = True

                return HttpResponse(json.dumps(resp), status=status.HTTP_200_OK)
            return HttpResponse(
                "Configuration does not exists", status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(
                "Information not valid", status=status.HTTP_400_BAD_REQUEST
            )
