import json
from django.http import JsonResponse
import os
import sys
import logging
import copy
import traceback
import requests
import re
from uuid import uuid4

from django.http import HttpResponse
from django.views import View
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import DatasourceSerializer, ModelSourceSerializer
from automl.models import Datasource, ModelSource

from confluent_kafka import Producer

def is_blank(attribute):
    """Checks if the attribute is an empty string or None.
        Args:
            attribute (str): Attribute to check
        Returns:
            boolean: whether attribute is blank or not
    """
    return attribute is None or attribute == ''

def kubernetes_config( token=None, external_host=None ):
    """ Get Kubernetes configuration.
        You can provide a token and the external host IP 
        to access a external Kubernetes cluster. If one
        of them is not provided the configuration returned
        will be for your local machine.
        Parameters:
            str: token 
            str: external_host (e.g. "https://192.168.65.3:6443")
        Return:
            Kubernetes API client
    """
    aConfiguration = client.Configuration()
    if token != None and \
        external_host != None:

        aConfiguration.host = external_host 
        aConfiguration.verify_ssl = False
        aConfiguration.api_key = { "authorization": "Bearer " + token }
    api_client = client.ApiClient( aConfiguration) 
    return api_client

def parse_kwargs_fit(kwargs_fit):
    """Converts kwargs_fit to a dictionary string
            kwargs_fit (str): Arguments for training.
            Example:
                epochs=5, steps_per_epoch=1000
        Returns:
            str: kwargs_fit formatted as string JSON
    """
    dic = {}
    if kwargs_fit != None and kwargs_fit != '':
        kwargs_fit=kwargs_fit.replace(" ", "")
        for l in kwargs_fit.split(","):
            pair=l.split('=')
            dic[pair[0]]=eval(pair[1])
    
    return json.dumps(dic)

def check_colission(datasource_item, model_item):
    """Checks if the datasource and the model are compatible"""

    ds_input_config = json.loads(datasource_item['input_config'])

    if ds_input_config['data_reshape'] == model_item['input_shape'] and \
        json.loads(datasource_item['dataset_restrictions']) == json.loads(model_item['data_restriction']) and \
        datasource_item['total_msg'] >= model_item['min_data']:
        return True
    
    return False

def deploy_on_kubernetes(datasource_item, model_item, framework):
    try:
        """KUBERNETES code goes here"""
        config.load_incluster_config() # To run inside the container
        # config.load_kube_config() # To run externally
        logging.info("Connection to Kubernetes %s %s", os.environ.get('KUBE_TOKEN'), os.environ.get('KUBE_HOST'))
        api_client = kubernetes_config(token=os.environ.get('KUBE_TOKEN'), external_host=os.environ.get('KUBE_HOST'))
        api_instance = client.BatchV1Api(api_client)
        # api_instance = client.BatchV1Api()

        # TODO: Conforme incrementen los frameworks y las distintas combinaciones de metodologias, introducir aquí su imagen y sus parámetros
        if framework == "tf":
            image = settings.TENSORFLOW_FEDERATED_TRAINING_MODEL_IMAGE
        elif framework == "pth":
            image = settings.PYTORCH_FEDERATED_TRAINING_MODEL_IMAGE
        else:
            raise NotImplementedError("Framework/metodology not implemented")
        
        federated_string_id = str(model_item['federated_string_id'])

        job_manifest = {
                        'apiVersion': 'batch/v1',
                        'kind': 'Job',
                        'metadata': { # random id
                            'name': f'federated-training-{federated_string_id}-worker-{uuid4().hex[:8]}',
                        },
                        'spec': {
                            'ttlSecondsAfterFinished' : 10,
                            'template' : {
                                'spec': {
                                    'containers': [{
                                        'image': image,
                                        'name': 'training',
                                        'env': [{'name': 'KML_CLOUD_BOOTSTRAP_SERVERS', 'value': settings.KML_CLOUD_BOOTSTRAP_SERVERS},
                                                {'name': 'DATA_BOOTSTRAP_SERVERS', 'value': settings.FEDERATED_BOOTSTRAP_SERVERS},
                                                {'name': 'DATA_TOPIC', 'value': datasource_item['topic']},
                                                {'name': 'INPUT_FORMAT', 'value': datasource_item['input_format']},
                                                {'name': 'INPUT_CONFIG', 'value': datasource_item['input_config']},
                                                {'name': 'VALIDATION_RATE', 'value': str(datasource_item['validation_rate'])},
                                                {'name': 'TEST_RATE', 'value': str(datasource_item['test_rate'])},
                                                {'name': 'TOTAL_MSG', 'value': str(datasource_item['total_msg'])},                                                
                                                {'name': 'FEDERATED_MODEL_ID', 'value': federated_string_id},
                                                {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"},
                                                ],
                                    }],
                                    'imagePullPolicy': 'Always', #'IfNotPresent', # TODO: Remove this when the image is in DockerHub
                                    'restartPolicy': 'OnFailure'
                                }
                            }
                        }
                    }        
                
        logging.debug("Job manifest: %s", job_manifest)
        resp = api_instance.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
        return HttpResponse(status=status.HTTP_201_CREATED)
    except Exception as e:
        traceback.print_exc()
        logging.error(str(e))
        return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)     


class DatasourceList(generics.ListCreateAPIView):
    """View to get the list of datasources and create a new datasource
        
        URL: /federated-datasources
    """

    queryset = Datasource.objects.all()
    serializer_class = DatasourceSerializer

    def post(self, request, format=None):
        try:            

            data = json.loads(request.body)

            logging.info("Received data: %s", data)            
            ds_serializer = DatasourceSerializer(data=data)
            
            if ds_serializer.is_valid():
                """Checks if data received is valid"""
                # save data to database
                logging.info("Data received is valid. Saving to database...")
                ds_serializer.save()

                """Checks for all datasources if there is a model that can be trained"""
                modelsources = ModelSource.objects.all()
                logging.info("Checking for models that can be trained...")
                for modelsource in modelsources:
                    ms_serializer = ModelSourceSerializer(modelsource)                    
                    has_collided = check_colission(ds_serializer.data, ms_serializer.data)

                    if has_collided:
                        logging.info("Datasource and model are compatible. Deploying model...")
                        deploy_on_kubernetes(ds_serializer.data, ms_serializer.data, ms_serializer.data['framework'])

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse('Deployment not valid', status=status.HTTP_406_NOT_ACCEPTABLE)
        except Exception as e:
            traceback.print_exc()
            print(str(e))
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)


        
class ModelFromControlLogger(generics.ListCreateAPIView):
    """View to create a new datasource and send it to kafka
        
        URL: /model-control-logger
    """
    queryset = ModelSource.objects.all()
    serializer_class = ModelSourceSerializer

    def post(self, request, format=None):
        try:

            data = json.loads(request.body)         

            parsed_data = {'federated_string_id': data['federated_params']['federated_string_id'],
                            'data_restriction': data['federated_params']['data_restriction'],
                            'min_data': data['federated_params']['min_data'],
                            'input_shape': data['model_format']['input_shape'],
                            'output_shape': data['model_format']['output_shape'],
                        }
            
            logging.info("Received data: %s", parsed_data)               
            ms_serializer = ModelSourceSerializer(data=parsed_data)
            
            if ms_serializer.is_valid():
                """Checks if data received is valid"""
                # save data to database
                logging.info("Data received is valid. Saving to database...")
                ms_serializer.save()

                """Checks for all datasources if there is a model that can be trained"""
                datasources = Datasource.objects.all()
                logging.info("Checking for datasources that can be used to train the model...")
                for datasource in datasources:
                    # Parse to JSON
                    ds_serializer = DatasourceSerializer(datasource)
                    
                    has_collided = check_colission(ds_serializer.data, ms_serializer.data)
                    if has_collided:
                        logging.info("Datasource and model are compatible. Deploying model...")
                        deploy_on_kubernetes(ds_serializer.data, ms_serializer.data, ms_serializer.data['framework'])

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse('Deployment not valid', status=status.HTTP_406_NOT_ACCEPTABLE)
        except Exception as e:
            traceback.print_exc()
            print(str(e))
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)