import json
from django.http import JsonResponse
import os
import sys
import logging
import copy
import traceback
import requests
import re

from django.http import HttpResponse
from django.views import View
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import MLModelSerializer, ConfigurationSerializer, DeploymentSerializer, DatasourceSerializer
from automl.serializers import TrainingResultSerializer, SimpleResultSerializer, DeployDeploymentSerializer, DeployInferenceSerializer
from automl.serializers import InferenceSerializer, SimplerResultSerializer

from automl.models import MLModel, Deployment, Configuration, TrainingResult, Datasource, Inference

from confluent_kafka import Producer

def is_blank(attribute):
    """Checks if the attribute is an empty string or None.
        Args:
            attribute (str): Attribute to check
        Returns:
            boolean: whether attribute is blank or not
    """
    return attribute is None or attribute == ''

def kubernetes_config(token=None, external_host=None):
    """Get Kubernetes configuration.
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
    if token != None and external_host != None:
        aConfiguration.host = external_host 
        aConfiguration.verify_ssl = False
        aConfiguration.api_key = {"authorization": "Bearer " + token}
    
    api_client = client.ApiClient(aConfiguration) 
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

def delete_deploy(inference_id, token=None, external_host=None):
    """ Delete a previous deployment.
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
        name='model-inference-'+str(inference_id),
        namespace=settings.KUBE_NAMESPACE,
        body=client.V1DeleteOptions(
            propagation_policy='Foreground',
            grace_period_seconds=5))
    return api_response

class ModelList(generics.ListCreateAPIView):
    """View to get the list of models and create a new model
        
        URL: /models
    """

    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer

    def post(self, request, format=None):
        """ Expects a JSON in the request body with the information to create a new model.

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
            logging.info("Data code received %s", data['code'])

            imports_code = '' if 'imports' not in data else data['imports']

            if 'distributed' in data:
                data_to_send = {"imports_code": imports_code, "model_code": data['code'], "distributed": data['distributed'], "request_type": "check"}
            else:             
                data_to_send = {"imports_code": imports_code, "model_code": data['code'], "distributed": False, "request_type": "check"}
                                     
            if data['framework'] == "pth":
                resp = requests.post(settings.PYTORCH_EXECUTOR_URL+"exec_pth/",data=json.dumps(data_to_send))
            else:   
                resp = requests.post(settings.TENSORFLOW_EXECUTOR_URL+"exec_tf/",data=json.dumps(data_to_send))

            """Prints the information of the model"""
            if resp.status_code == 200:
                serializer = MLModelSerializer(data=data)
                if serializer.is_valid():
                    obj=serializer.save()
                    return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse("Information not valid", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

class DistributedModelList(generics.ListAPIView):
    """View to get the list of distributed models
        
        URL: /models/distributed
    """

    queryset = MLModel.objects.filter(distributed = True)
    serializer_class = MLModelSerializer

class FatherModelList(generics.ListAPIView):
    """View to get the list of models which have no father
        
        URL: /models/fathers
    """

    queryset = MLModel.objects.filter(father = None)
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
                    if data['code'] != model_obj.code or data['framework'] != model_obj.framework:
                        imports_code = '' if 'imports' not in data else data['imports']
                        
                        if 'distributed' in data:
                            data_to_send = {"imports_code": imports_code, "model_code": data['code'], "distributed": data['distributed'], "request_type": "check"}
                        else:
                            data_to_send = {"imports_code": imports_code, "model_code": data['code'], "distributed": False, "request_type": "check"}
                            
                        if data['framework'] == "pth":
                            resp = requests.post(settings.PYTORCH_EXECUTOR_URL+"exec_pth/",data=json.dumps(data_to_send))
                        else:   
                            resp = requests.post(settings.TENSORFLOW_EXECUTOR_URL+"exec_tf/",data=json.dumps(data_to_send))

                        """Prints the information of the model"""
                        if resp.status_code != 200:
                            return HttpResponse('Model not valid.', status=status.HTTP_400_BAD_REQUEST)
                    serializer.save()
                    return HttpResponse(status=status.HTTP_200_OK)
                else:
                    return HttpResponse("Information not valid", status=status.HTTP_400_BAD_REQUEST)
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Information not valid', status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, format=None):
        """Deletes a model"""
        try:
            if MLModel.objects.filter(pk=pk).exists():
                model_obj = MLModel.objects.get(pk=pk)
                if Configuration.objects.filter(ml_models=model_obj).exists():
                    return HttpResponse('Model cannot be deleted since it is used in a configuration. Consider to delete the configuration.', 
                    status=status.HTTP_400_BAD_REQUEST)     
                model_obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Model does not exist", status=status.HTTP_400_BAD_REQUEST)
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
            return HttpResponse('TrainingResult not found', status=status.HTTP_400_BAD_REQUEST)

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
            models = data['ml_models']
            all_models = []
            for m in models:
                all_models.append(m)
                obj = MLModel.objects.get(pk=m)
                if hasattr(obj, 'child'):
                    son = obj.child
                    while son:
                        all_models.append(son.id)
                        if hasattr(son, 'child'):
                            son = son.child
                        else:
                            son = None
            data['ml_models'] = all_models
            serializer = ConfigurationSerializer(data=data)
            if serializer.is_valid():
                obj = serializer.save()
                return HttpResponse(status=status.HTTP_201_CREATED)
            else:
                return HttpResponse("Information not valid", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Configuration not valid', status=status.HTTP_400_BAD_REQUEST)

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
                models = data['ml_models']
                all_models = []
                for m in models:
                    all_models.append(m)
                    obj = MLModel.objects.get(pk=m)
                    if hasattr(obj, 'child'):
                        son = obj.child
                        while son:
                            all_models.append(son.id)
                            if hasattr(son, 'child'):
                                son = son.child
                            else:
                                son = None
                data['ml_models'] = all_models
                configuration_obj = Configuration.objects.get(pk=pk)
                serializer = ConfigurationSerializer(configuration_obj, data=data)
                if serializer.is_valid():
                    serializer.save()
                    return HttpResponse(status=status.HTTP_200_OK)
                else:
                    return HttpResponse("Information not valid", status=status.HTTP_400_BAD_REQUEST)
            else:
                return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Information not valid', status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Deletes a configuration"""
        try:
            if Configuration.objects.filter(pk=pk).exists():
                obj = Configuration.objects.get(pk=pk)
                if Deployment.objects.filter(configuration=obj).exists():
                    return HttpResponse('Configuration cannot be deleted since it is used by a deployment. Consider to delete the deployment.',
                            status=status.HTTP_400_BAD_REQUEST)
                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Model does not exist", status=status.HTTP_400_BAD_REQUEST)
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

                return HttpResponse(json.dumps(list(frameworks_used)), status=status.HTTP_200_OK)
            return HttpResponse('Configuration does not exist', status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Information not valid', status=status.HTTP_400_BAD_REQUEST)

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
            return HttpResponse('Configuration does not exists', status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Information not valid', status=status.HTTP_400_BAD_REQUEST)

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
            gpu_mem_to_allocate = data['gpumem']
            data.pop('gpumem')
            
            # tf_kwargs verification
            tf_kwargs_fit_empty, tf_kwargs_val_empty = False, False
            if data['tf_kwargs_fit'] != '':
                tf_kwargs_fit_empty = False
                if data['tf_kwargs_val'] == '':
                    tf_kwargs_val_empty = True
                    data.pop('tf_kwargs_val') 
            else:
                data.pop('tf_kwargs_fit') 
                data.pop('tf_kwargs_val')
                tf_kwargs_fit_empty, tf_kwargs_val_empty = True, True

            # pth_kwargs verification
            pth_kwargs_fit_empty, pth_kwargs_val_empty = False, False
            if data['pth_kwargs_fit'] != '':
                pth_kwargs_fit_empty = False
                if data['pth_kwargs_val'] == '':
                    pth_kwargs_val_empty = True
                    data.pop('pth_kwargs_val') 
            else:
                data.pop('pth_kwargs_fit') 
                data.pop('pth_kwargs_val')
                pth_kwargs_fit_empty, pth_kwargs_val_empty = True, True

            serializer = DeployDeploymentSerializer(data=data)
            if serializer.is_valid():
                try:
                    """KUBERNETES code goes here"""
                    config.load_incluster_config() # To run inside the container
                    # config.load_kube_config() # To run externally
                    logging.info("Connection to Kubernetes %s %s", os.environ.get('KUBE_TOKEN'), os.environ.get('KUBE_HOST'))
                    api_client = kubernetes_config(token=os.environ.get('KUBE_TOKEN'), external_host=os.environ.get('KUBE_HOST'))
                    api_instance = client.BatchV1Api(api_client)
                    # api_instance = client.BatchV1Api()
                    
                    if not tf_kwargs_fit_empty:
                        # TensorFlow Verification
                        tf_kwargs_fit  = parse_kwargs_fit(data['tf_kwargs_fit'])
                        tf_kwargs_val  = parse_kwargs_fit(data['tf_kwargs_val']) if not tf_kwargs_val_empty else json.dumps({})

                        data_to_send = {"batch": data['batch'], "kwargs_fit": tf_kwargs_fit, "kwargs_val": tf_kwargs_val}
                        tf_resp = requests.post(settings.TENSORFLOW_EXECUTOR_URL+"check_deploy_config/", data=json.dumps(data_to_send))
                        if tf_resp.status_code != 200:
                            raise ValueError('Some TensorFlow arguments are not valid.')
                        
                        if 'incremental' in data.keys() and data['incremental'] == True:
                            if 'numeratorBatch' in data.keys() and 'denominatorBatch' in data.keys() and data['numeratorBatch'] >= data['denominatorBatch']:
                                raise ValueError('Arguments numerator and denominator batch are not valid.')

                            if 'indefinite' in data.keys() and data['indefinite'] == True:
                                if Configuration.objects.filter(pk=data['configuration']).exists():
                                    obj = Configuration.objects.get(pk=data['configuration'])
                                    for m in obj.ml_models.all():
                                        if not m.distributed:
                                            if not data['monitoring_metric'] in m.code:
                                                raise ValueError('Monitoring metric does not match.')

                    if not pth_kwargs_fit_empty:
                        # PyTorch Verification
                        pth_kwargs_fit = parse_kwargs_fit(data['pth_kwargs_fit'])
                        pth_kwargs_val = parse_kwargs_fit(data['pth_kwargs_val']) if not pth_kwargs_val_empty else json.dumps({})

                        data_to_send = {"batch": data['batch'], "kwargs_fit": pth_kwargs_fit, "kwargs_val": pth_kwargs_val}
                        pth_resp = requests.post(settings.PYTORCH_EXECUTOR_URL+"check_deploy_config/", data=json.dumps(data_to_send))
                        if pth_resp.status_code != 200:
                            raise ValueError('Some PyTorch arguments are not valid.')
                                        
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
                                case = 1
                            else:
                                case = 2
                        else:
                            if not deployment.incremental:
                                case = 3
                            else:
                                case = 4
                        
                        if not result.model.distributed:
                            if not deployment.incremental:
                                job_manifest = {
                                    'apiVersion': 'batch/v1',
                                    'kind': 'Job',
                                    'metadata': {
                                        'name': 'model-training-'+str(result.id)
                                    },
                                    'spec': {
                                        'ttlSecondsAfterFinished' : 10,
                                        'template' : {
                                            'spec': {
                                                'containers': [{
                                                    'image': image,
                                                    'name': 'training',
                                                    'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                            {'name': 'RESULT_URL', 'value': str(os.environ.get('BACKEND_URL'))+'/results/'+str(result.id)},
                                                            {'name': 'RESULT_ID', 'value': str(result.id)},
                                                            {'name': 'CONTROL_TOPIC', 'value': settings.CONTROL_TOPIC},
                                                            {'name': 'DEPLOYMENT_ID', 'value': str(deployment.id)},
                                                            {'name': 'BATCH', 'value': str(deployment.batch)},
                                                            {'name': 'KWARGS_FIT', 'value': kwargs_fit},
                                                            {'name': 'KWARGS_VAL', 'value': kwargs_val},
                                                            {'name': 'CONF_MAT_CONFIG', 'value': json.dumps(deployment.conf_mat_settings)},
                                                            {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"},  ##  (Sharing GPU)
                                                            {'name': 'CASE', 'value': str(case)}
                                                            ],
                                                    'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                }],
                                                'imagePullPolicy': 'IfNotPresent', # TODO: Remove this when the image is in DockerHub
                                                'restartPolicy': 'OnFailure'
                                            }
                                        }
                                    }
                                }
                                resp = api_instance.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
                            else:
                                job_manifest = {
                                    'apiVersion': 'batch/v1',
                                    'kind': 'Job',
                                    'metadata': {
                                        'name': 'incremental-model-training-'+str(result.id)
                                    },
                                    'spec': {
                                        'ttlSecondsAfterFinished' : 10,
                                        'template' : {
                                            'spec': {
                                                'containers': [{
                                                    'image': image,
                                                    'name': 'training',
                                                    'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                            {'name': 'RESULT_URL', 'value': str(os.environ.get('BACKEND_URL'))+'/results/'+str(result.id)},
                                                            {'name': 'RESULT_ID', 'value': str(result.id)},
                                                            {'name': 'CONTROL_TOPIC', 'value': settings.CONTROL_TOPIC},
                                                            {'name': 'DEPLOYMENT_ID', 'value': str(deployment.id)},
                                                            {'name': 'BATCH', 'value': str(deployment.batch)},
                                                            {'name': 'KWARGS_FIT', 'value': kwargs_fit},
                                                            {'name': 'KWARGS_VAL', 'value': kwargs_val},
                                                            {'name': 'CONF_MAT_CONFIG', 'value': json.dumps(deployment.conf_mat_settings)},
                                                            {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"},  ##  (Sharing GPU)
                                                            {'name': 'CASE', 'value': str(case)},
                                                            {'name': 'STREAM_TIMEOUT', 'value': str(deployment.stream_timeout) if not deployment.indefinite else str(-1)},
                                                            {'name': 'MESSAGE_POLL_TIMEOUT', 'value': str(deployment.message_poll_timeout)},
                                                            {'name': 'MONITORING_METRIC', 'value': deployment.monitoring_metric},
                                                            {'name': 'CHANGE', 'value': deployment.change},
                                                            {'name': 'IMPROVEMENT', 'value': str(deployment.improvement)},
                                                            {'name': 'NUMERATOR_BATCH', 'value': str(deployment.numeratorBatch)},
                                                            {'name': 'DENOMINATOR_BATCH', 'value': str(deployment.denominatorBatch)}
                                                            ],
                                                    'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                }],
                                                'imagePullPolicy': 'IfNotPresent', # TODO: Remove this when the image is in DockerHub
                                                'restartPolicy': 'OnFailure'
                                            }
                                        }
                                    }
                                }
                                resp = api_instance.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
                        
                        elif result.model.distributed and result.model.father == None:
                            """Obteins all the distributed models from a deployment and creates a job for each group of them"""
                            result_urls = []
                            result_ids = []
                            s = str(os.environ.get('BACKEND_URL'))+'/results/'
                            n = ''

                            result_urls.append(s+str(result.id))
                            result_ids.append(str(result.id))
                            n += '-'+str(result.id)
                            current = result
                            while hasattr(current.model, 'child'):
                                current = TrainingResult.objects.get(model=current.model.child, deployment=deployment)
                                result_urls.append(s+str(current.id))
                                result_ids.append(str(current.id))
                                n += '-'+str(current.id)

                            result_urls.reverse()
                            result_ids.reverse()

                            if not deployment.incremental:
                                job_manifest = {
                                    'apiVersion': 'batch/v1',
                                    'kind': 'Job',
                                    'metadata': {
                                        'name': 'model-distributed-training'+n
                                    },
                                    'spec': {
                                        'ttlSecondsAfterFinished' : 10,
                                        'template' : {
                                            'spec': {
                                                'containers': [{
                                                    'image': image,
                                                    'name': 'training',
                                                    'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                            {'name': 'RESULT_URL', 'value': str(result_urls)},
                                                            {'name': 'RESULT_ID', 'value': str(result_ids)},
                                                            {'name': 'CONTROL_TOPIC', 'value': settings.CONTROL_TOPIC},
                                                            {'name': 'DEPLOYMENT_ID', 'value': str(deployment.id)},
                                                            {'name': 'OPTIMIZER', 'value': deployment.optimizer},
                                                            {'name': 'LEARNING_RATE', 'value': str(deployment.learning_rate)},
                                                            {'name': 'LOSS', 'value': deployment.loss},
                                                            {'name': 'METRICS', 'value': deployment.metrics},
                                                            {'name': 'BATCH', 'value': str(deployment.batch)},
                                                            {'name': 'KWARGS_FIT', 'value': kwargs_fit},
                                                            {'name': 'KWARGS_VAL', 'value': kwargs_val},
                                                            {'name': 'CONF_MAT_CONFIG', 'value': json.dumps(deployment.conf_mat_settings)},
                                                            {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"},  ##  (Sharing GPU)
                                                            {'name': 'CASE', 'value': str(case)}
                                                            ],
                                                    'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                }],
                                                'imagePullPolicy': 'IfNotPresent', # TODO: Remove this when the image is in DockerHub
                                                'restartPolicy': 'OnFailure'
                                            }
                                        }
                                    }
                                }                                
                                resp = api_instance.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
                            else:
                                job_manifest = {
                                    'apiVersion': 'batch/v1',
                                    'kind': 'Job',
                                    'metadata': {
                                        'name': 'incremental-model-distributed-training'+n
                                    },
                                    'spec': {
                                        'ttlSecondsAfterFinished' : 10,
                                        'template' : {
                                            'spec': {
                                                'containers': [{
                                                    'image': image,
                                                    'name': 'training',
                                                    'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                            {'name': 'RESULT_URL', 'value': str(result_urls)},
                                                            {'name': 'RESULT_ID', 'value': str(result_ids)},
                                                            {'name': 'CONTROL_TOPIC', 'value': settings.CONTROL_TOPIC},
                                                            {'name': 'DEPLOYMENT_ID', 'value': str(deployment.id)},
                                                            {'name': 'OPTIMIZER', 'value': deployment.optimizer},
                                                            {'name': 'LEARNING_RATE', 'value': str(deployment.learning_rate)},
                                                            {'name': 'LOSS', 'value': deployment.loss},
                                                            {'name': 'METRICS', 'value': deployment.metrics},
                                                            {'name': 'BATCH', 'value': str(deployment.batch)},
                                                            {'name': 'KWARGS_FIT', 'value': kwargs_fit},
                                                            {'name': 'KWARGS_VAL', 'value': kwargs_val},
                                                            {'name': 'CONF_MAT_CONFIG', 'value': json.dumps(deployment.conf_mat_settings)},
                                                            {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"},  ##  (Sharing GPU)
                                                            {'name': 'CASE', 'value': str(case)},
                                                            {'name': 'STREAM_TIMEOUT', 'value': str(deployment.stream_timeout) if not deployment.indefinite else str(-1)},
                                                            {'name': 'MESSAGE_POLL_TIMEOUT', 'value': str(deployment.message_poll_timeout)},
                                                            {'name': 'IMPROVEMENT', 'value': str(deployment.improvement)},
                                                            {'name': 'NUMERATOR_BATCH', 'value': str(deployment.numeratorBatch)},
                                                            {'name': 'DENOMINATOR_BATCH', 'value': str(deployment.denominatorBatch)}
                                                            ],
                                                    'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                }],
                                                'imagePullPolicy': 'IfNotPresent', # TODO: Remove this when the image is in DockerHub
                                                'restartPolicy': 'OnFailure'
                                            }
                                        }
                                    }
                                }
                                resp = api_instance.create_namespaced_job(body=job_manifest, namespace=settings.KUBE_NAMESPACE)
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
                    return HttpResponse('Deployment cannot be deleted. Please delete its training results first.',
                            status=status.HTTP_400_BAD_REQUEST)
                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Deployment does not exist", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

class TrainingResultList(generics.ListAPIView):
    """View to get the list of results
        
        URL: /results
    """
    queryset = TrainingResult.objects.all()
    serializer_class = TrainingResultSerializer

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
            return HttpResponse('Deployment not found', status=status.HTTP_400_BAD_REQUEST)

class DownloadTrainedModel(generics.RetrieveAPIView):
    """View to download a trained model
        
        URL: GET /results/model/{:id_result} to get the model file trained.
    """
    def get(self, request, pk, format=None):
        try:
            result= TrainingResult.objects.get(pk=pk)  
            filename = os.path.join(settings.MEDIA_ROOT, result.trained_model.name)
            """Obtains the trained model filename"""

            with open(filename, 'rb') as f:
                file_data = f.read()
                file_ext = None
                if result.model.framework == "tf":
                    file_ext = "h5"
                elif result.model.framework == "pth":
                    file_ext = "pth"
                response = HttpResponse(file_data, content_type='application/force-download')

                response['Content-Disposition'] = f'attachment; filename="model.{file_ext}"'
                response['Access-Control-Expose-Headers'] = "ML-Framework"
                response['ML-Framework'] = result.model.framework

                return response


        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

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
                data_to_send = {"imports_code": result.model.imports, "model_code": result.model.code, "distributed": result.model.distributed, "request_type": "load_model"}
                resp = requests.post(settings.TENSORFLOW_EXECUTOR_URL+"exec_tf/",data=json.dumps(data_to_send))
                """Saves the model temporally"""

                response = HttpResponse(resp.content, content_type='application/model')
                response['Content-Disposition'] = 'attachment; filename="model.h5"'
            elif result.model.framework == "pth":
                response = HttpResponse(result.model.code)

            if result.status !=  TrainingResult.STATUS.finished:
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
        if request.FILES['trained_model'] and TrainingResult.objects.filter(pk=pk).exists():
            try:
                data = json.loads(request.data['data'])
                obj = TrainingResult.objects.get(id=pk)

                if data['indefinite'] == True:
                    deployment = obj.deployment
                    model = obj.model
                    obj = TrainingResult.objects.create(deployment=deployment, model=model)
                    
                data.pop('indefinite')
                serializer = SimpleResultSerializer(obj, data = data, partial=True)
                
                if serializer.is_valid():
                    serializer.save()
                else:
                    logging.info("Cannot save training result")
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

                trained_model = request.FILES['trained_model']
                if not obj.model.distributed:
                    confussion_matrix = request.FILES['confussion_matrix'] if obj.deployment.conf_mat_settings and obj.test_metrics != {} else None
                else:
                    confussion_matrix = None
                
                fs = FileSystemStorage()
                path = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)
                
                if confussion_matrix != None:
                    if os.path.exists(path+str(obj.id)+'.png'):
                        os.remove(path+str(obj.id)+'.png')

                    filename = fs.save(path+str(obj.id)+'.png', confussion_matrix)
                    obj.confusion_mat_img.name=(settings.TRAINED_MODELS_DIR+str(obj.id)+'.png')

                if obj.model.framework == "tf":
                    if os.path.exists(path+str(obj.id)+'.h5'):
                        os.remove(path+str(obj.id)+'.h5')
                    
                    filename = fs.save(path+str(obj.id)+'.h5', trained_model)
                    obj.trained_model.name=(settings.TRAINED_MODELS_DIR+str(obj.id)+'.h5')
                elif obj.model.framework == "pth":
                    if os.path.exists(path+str(obj.id)+'.pth'):
                        os.remove(path+str(obj.id)+'.pth')
                    
                    filename = fs.save(path+str(obj.id)+'.pth', trained_model)
                    obj.trained_model.name=(settings.TRAINED_MODELS_DIR+str(obj.id)+'.pth')

                obj.status = TrainingResult.STATUS.finished
                obj.save()
                return HttpResponse(status=status.HTTP_200_OK)
            except Exception as e:
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse('File not found', status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Deletes a training result"""
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                obj = TrainingResult.objects.get(pk=pk)
                if obj.status not in ['finished', 'stopped']:
                    return HttpResponse('Training result in use, please stop it before delete.',
                            status=status.HTTP_400_BAD_REQUEST)
                
                filename = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)+str(obj.id)+'.h5'
                """Obtains the model filename"""
                
                if os.path.exists(filename):
                    os.remove(filename)
                """Deletes the trained model"""

                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Result does not exist", status=status.HTTP_400_BAD_REQUEST)
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
                data = json.loads(request.data['data'])
                obj = TrainingResult.objects.get(id=pk)
                serializer = SimplerResultSerializer(obj, data = data, partial=True)
                
                if serializer.is_valid():
                    serializer.save()
                else:
                    logging.info("Cannot save training result")
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

                obj.save()
                return HttpResponse(status=status.HTTP_200_OK)
            except Exception as e:
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse('Training result does not exist', status=status.HTTP_400_BAD_REQUEST)

class InferenceList(generics.ListCreateAPIView):
    """View to get the list of inferences
        
        URL: /inferences
    """
    queryset = Inference.objects.all()
    serializer_class = InferenceSerializer

class TrainingResultStop(generics.CreateAPIView):
    """View to stop from Kubernetes and delete a training result
        
        URL: /inferences/{:id_inference}
    """
    
    def post(self, request, pk, format=None):
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                result = TrainingResult.objects.get(pk=pk)
                if result.status == 'deployed':
                    try:
                        config.load_incluster_config() # To run inside the container
                        #config.load_kube_config() # To run externally
                        #api_instance = client.BatchV1Api()
                        api_client = kubernetes_config(token=os.environ.get('KUBE_TOKEN'), external_host=os.environ.get('KUBE_HOST'))
                        api_instance = client.BatchV1Api( api_client)

                        api_response = api_instance.delete_namespaced_job(
                        name='model-training-'+str(result.id),
                        namespace=settings.KUBE_NAMESPACE,
                        body=client.V1DeleteOptions(
                            propagation_policy='Foreground',
                            grace_period_seconds=5))
                    except:
                        pass
                    result.status = 'stopped'
                    result.save()
                    return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Result not found or not running", status=status.HTTP_400_BAD_REQUEST)
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
                        epoch_train_met = {"value": obj.train_metrics[metric][n_epoch], "name": n_epoch+1}
                        met_train["series"].append(epoch_train_met)
                        
                    if existsValid:
                        for n_epoch in range(len(obj.val_metrics[metric])):
                            epoch_valid_met = {"value": obj.val_metrics[metric][n_epoch], "name": n_epoch+1}
                            met_val["series"].append(epoch_valid_met)    
                    
                    res.append(met_train)

                    if existsValid:
                        res.append(met_val)

                response = json.dumps({'metrics': res, 'conf_mat': obj.confusion_matrix})

                return HttpResponse(response, status=status.HTTP_200_OK)
            return HttpResponse('Training result does not exist', status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Information not valid', status=status.HTTP_400_BAD_REQUEST)

class DownloadConfussionMatrix(generics.RetrieveAPIView):
    """View to get the confusion matrix of a result.
        
        URL: GET /results/confusion_matrix/{:id_result} to get the confusion matrix of a result
    """
    def get(self, request, pk, format=None):
        try:
            result= TrainingResult.objects.get(pk=pk)  
            filename = os.path.join(settings.MEDIA_ROOT, result.confusion_mat_img.name)
            """Obtains the confusion matrix filename"""

            with open(filename, 'rb') as f:
                file_data = f.read()
                response = HttpResponse(file_data, content_type='application/image')

                response['Content-Disposition'] = 'attachment; filename="confusion_mat.png'
                return response

        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

class InferenceStopDelete(generics.RetrieveUpdateDestroyAPIView):
    """View to stop from Kubernetes and delete an inference
        
        URL: /inferences/{:id_inference}
    """
    queryset = Inference.objects.all()
    serializer_class = InferenceSerializer
    
    def post(self, request, pk, format=None):
        try:
            if Inference.objects.filter(pk=pk).exists():
                inference = Inference.objects.get(pk=pk)
                if inference.status == 'deployed':
                    try:
                        config.load_incluster_config() # To run inside the container
                        #config.load_kube_config() # To run externally
                        #api_instance = client.CoreV1Api()
                        if not is_blank(inference.external_host) and not is_blank(inference.token):
                            token=inference.token
                            external_host=inference.external_host
                        else:
                            token=os.environ.get('KUBE_TOKEN')
                            external_host=os.environ.get('KUBE_HOST')

                        api_client = kubernetes_config(token=token, external_host=external_host)                       
                        api_instance = client.CoreV1Api( api_client)

                        api_response = api_instance.delete_namespaced_replication_controller(
                        name='model-inference-'+str(inference.id),
                        namespace=settings.KUBE_NAMESPACE,
                        body=client.V1DeleteOptions(
                            propagation_policy='Foreground',
                            grace_period_seconds=5))
                    except:
                        pass
                    inference.status = 'stopped'
                    inference.save()
                    return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Inference not found or not running", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Deletes an inference"""
        try:
            if Inference.objects.filter(pk=pk).exists():
                obj = Inference.objects.get(pk=pk)
                if obj.status not in ['stopped']:
                    return HttpResponse('Inference in use, please stop it before delete.',
                            status=status.HTTP_400_BAD_REQUEST)
                obj.delete()
                return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Inference does not exist", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

class InferenceResultID(generics.ListCreateAPIView):
    """View to get information and deploy a new inference from a training result
        
        URL: /results/inference/{:id_result}
    """
    
    def get(self, request, pk, format=None):
        """ Checks if the training result exists and returns the input format and configuration if there any in other inference or 
            datasource objects to facilitate the inference deployment.
        """
        try:
            if TrainingResult.objects.filter(pk=pk).exists():
                response = {
                    'input_format': '',
                    'input_config': '',
                }
                result = TrainingResult.objects.get(id=pk)
                inferences = Inference.objects.filter(model_result=result)
                if inferences.count() > 0:
                    response['input_format']=inferences[0].input_format
                    response['input_config']=inferences[0].input_config
                else:
                    model = result.model
                    datasources = Datasource.objects.filter(deployment=str(result.deployment.id))

                    if datasources.count() > 0:
                        response['input_format'] = datasources[0].input_format
                        input_config = datasources[0].input_config

                        if not hasattr(model, 'child'):
                            response['input_config'] = input_config # TODO change to input_config
                        else:

                            data_to_send = {"imports_code": model.imports, "model_code": model.code, "distributed": model.distributed, "request_type": "input_shape"}
                            resp = requests.post(settings.TENSORFLOW_EXECUTOR_URL+"exec_tf/",data=json.dumps(data_to_send))

                            input_shape = resp.content.decode("utf-8")

                            sub = re.search(', (.+?)\)', input_shape)

                            if sub:
                                shape = sub.group(1)

                                dictionary = json.loads(input_config)

                                dictionary['data_reshape'] = shape.replace(',','')

                                new_input_config = json.dumps(dictionary)

                                response['input_config'] = new_input_config
                            else:
                                response['input_config'] = input_config
                            
                            if new_input_config == None:
                                dic = json.loads(input_config)
                            else:
                                dic = json.loads(new_input_config)
                                    
                            dic['data_type'] = 'float32'
                            aux_input_config = json.dumps(dic)
                            response['input_config'] = aux_input_config
                return HttpResponse(json.dumps(response), status=status.HTTP_200_OK)
        except Exception as e:
            traceback.print_exc()
            return HttpResponse('Result not found', status=status.HTTP_400_BAD_REQUEST)

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
                gpu_mem_to_allocate = data['gpumem']
                data.pop('gpumem')
                result = TrainingResult.objects.get(id=pk)
                serializer = DeployInferenceSerializer(data = data)
                
                if serializer.is_valid() and result.status == 'finished':
                    inference = serializer.save()
                    try:
                        config.load_incluster_config() # To run inside the container
                        # config.load_kube_config() # To run externally
                        # api_instance = client.CoreV1Api()

                        if not is_blank(inference.external_host) and not is_blank(inference.token):
                            token=inference.token
                            external_host=inference.external_host
                        else:                        
                            token=os.environ.get('KUBE_TOKEN')
                            external_host=os.environ.get('KUBE_HOST')

                        api_client = kubernetes_config(token=token, external_host=external_host)
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
                        logging.info("Input kafka broker is [%s] and output kafka broker is [%s]", input_kafka_broker, output_kafka_broker)

                        if result.model.framework == "tf":
                            image = settings.TENSORFLOW_INFERENCE_MODEL_IMAGE
                        elif result.model.framework == "pth":
                            image = settings.PYTORCH_INFERENCE_MODEL_IMAGE
                                                
                        if not result.model.distributed:
                            manifest = {
                                'apiVersion': 'v1', 
                                'kind': 'ReplicationController',
                                'metadata': {
                                    'name': 'model-inference-'+str(inference.id),
                                    'labels': {
                                        'name': 'model-inference-'+str(inference.id)
                                    }
                                },
                                'spec': {
                                    'replicas': inference.replicas,
                                    'selector': {
                                    # 'matchLabels': {
                                            'app' : 'inference'+str(inference.id)
                                        #}
                                    },
                                    'template':{
                                        'metadata':{
                                            'labels': {
                                                'app' : 'inference'+str(inference.id)
                                            }
                                        },
                                        'spec':{
                                            'containers': [{
                                                'image': image, 
                                                'name': 'inference',
                                                'env': [{'name': 'INPUT_BOOTSTRAP_SERVERS', 'value': input_kafka_broker},
                                                        {'name': 'OUTPUT_BOOTSTRAP_SERVERS', 'value': output_kafka_broker},                      
                                                        {'name': 'MODEL_ARCH_URL', 'value': str(os.environ.get('BACKEND_URL'))+'/results/'+str(result.id)},
                                                        {'name': 'MODEL_URL', 'value': str(os.environ.get('BACKEND_URL'))+'/results/model/'+str(result.id)},
                                                        {'name': 'INPUT_FORMAT', 'value': inference.input_format},
                                                        {'name': 'INPUT_CONFIG', 'value': inference.input_config},
                                                        {'name': 'INPUT_TOPIC', 'value': inference.input_topic},
                                                        {'name': 'OUTPUT_TOPIC', 'value': inference.output_topic},
                                                        {'name': 'GROUP_ID', 'value': 'inf'+str(result.id)},
                                                        {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"}  ##  (Sharing GPU)
                                                        ],
                                                'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                #'resources': {'limits':{'nvidia.com/gpu': 1}} ##  (Greedy GPU)
                                            }],
                                            'imagePullPolicy': 'IfNotPresent' # TODO: Remove this when the image is in DockerHub
                                        }
                                    }
                                }
                            }
                        else:
                            if not is_blank(inference.upper_kafka_broker):
                                upper_kafka_broker = inference.upper_kafka_broker
                            else:
                                upper_kafka_broker = settings.BOOTSTRAP_SERVERS

                            manifest = {
                                'apiVersion': 'v1', 
                                'kind': 'ReplicationController',
                                'metadata': {
                                    'name': 'model-inference-'+str(inference.id),
                                    'labels': {
                                        'name': 'model-inference-'+str(inference.id)
                                    }
                                },
                                'spec': {
                                    'replicas': inference.replicas,
                                    'selector': {
                                    # 'matchLabels': {
                                            'app' : 'inference'+str(inference.id)
                                        #}
                                    },
                                    'template':{
                                        'metadata':{
                                            'labels': {
                                                'app' : 'inference'+str(inference.id)
                                            }
                                        },
                                        'spec':{
                                            'containers': [{
                                                'image': settings.TENSORFLOW_INFERENCE_MODEL_IMAGE,
                                                'name': 'inference',
                                                'env': [{'name': 'INPUT_BOOTSTRAP_SERVERS', 'value': input_kafka_broker},
                                                        {'name': 'OUTPUT_BOOTSTRAP_SERVERS', 'value': output_kafka_broker},
                                                        {'name': 'UPPER_BOOTSTRAP_SERVERS', 'value': upper_kafka_broker},
                                                        {'name': 'MODEL_URL', 'value': str(os.environ.get('BACKEND_URL'))+'/results/model/'+str(result.id)},
                                                        {'name': 'INPUT_FORMAT', 'value': inference.input_format},
                                                        {'name': 'INPUT_CONFIG', 'value': inference.input_config},
                                                        {'name': 'INPUT_TOPIC', 'value': inference.input_topic},
                                                        {'name': 'OUTPUT_TOPIC', 'value': inference.output_topic},
                                                        {'name': 'OUTPUT_UPPER', 'value': inference.output_upper},
                                                        {'name': 'GROUP_ID', 'value': 'inf'+str(result.id)},
                                                        {'name': 'LIMIT', 'value': str(inference.limit)},
                                                        {'name': 'NVIDIA_VISIBLE_DEVICES', 'value': "all"}  ##  (Sharing GPU)
                                                        ],
                                                'resources': {'limits':{'aliyun.com/gpu-mem': gpu_mem_to_allocate}} ##  (Sharing GPU)
                                                #'resources': {'limits':{'nvidia.com/gpu': 1}} ##  (Greedy GPU)
                                            }],
                                            'imagePullPolicy': 'IfNotPresent' # TODO: Remove this when the image is in DockerHub
                                        }
                                    }
                                }
                            }
                        inference.save()
                        resp = api_instance.create_namespaced_replication_controller(body=manifest, namespace=settings.KUBE_NAMESPACE) # create_namespaced_deployment
                        return HttpResponse(status=status.HTTP_200_OK)
                    except Exception as e:
                        Inference.objects.filter(pk=inference.pk).delete()
                        return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
                return HttpResponse(status=status.HTTP_400_BAD_REQUEST)    
            except Exception as e:
                traceback.print_exc()
                return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse('Result not found', status=status.HTTP_400_BAD_REQUEST)

class DatasourceList(generics.ListCreateAPIView):
    """View to get the list of datasources and create a new datasource
        
        URL: /datasources
    """
    queryset = Datasource.objects.all()
    serializer_class = DatasourceSerializer

class DatasourceToKafka(generics.CreateAPIView):
    """View to create a new datasource and send it to kafka
        
        URL: /datasources/kafka
    """
    
    def post(self, request, format=None):
        """ Expects a JSON in the request body with the information to create a new datasource

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
            deployment_id = int(data['deployment'])
            if serializer.is_valid() and Deployment.objects.filter(pk=deployment_id).exists():
                """Checks if data received is valid and deployment received exists in the system"""
                
                conf = {'bootstrap.servers': settings.BOOTSTRAP_SERVERS} 
                producer = Producer(conf)
                """Creates a Kafka Producer to send the message to the control topic"""
                
                kafka_data = copy.deepcopy(data)
                del kafka_data['deployment']
                del kafka_data['time']
                """Deletes unused attributes"""
                
                kafka_data['input_config'] = json.loads(kafka_data['input_config'])

                key = bytes([deployment_id])
                data_bytes = json.dumps(kafka_data).encode('utf-8')

                logging.info("Control message to be sent to kafka control topic %s", kafka_data)

                producer.produce(settings.CONTROL_TOPIC, key=key, value=data_bytes)
                """Sends the data to Kafka"""
                producer.flush()
                """Waits until data is sent"""

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse('Deployment not valid', status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)