import json
import os
import sys
import logging
import copy
import traceback

import tensorflow as tf
from tensorflow import keras

from django.http import HttpResponse
from django.views import View
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from rest_framework import status
from rest_framework import generics

from kubernetes import client, config

from automl.serializers import MLModelSerializer, ConfigurationSerializer, DeploymentSerializer, DatasourceSerializer
from automl.serializers import TrainingResultSerializer, SimpleResultSerializer, DeployDeploymentSerializer, DeployInferenceSerializer
from automl.serializers import InferenceSerializer

from automl.models import MLModel, Deployment, Configuration, TrainingResult, Datasource, Inference

from kafka import KafkaProducer

def format_ml_code(code):
    """Checks if the ML code starts with the string 'model='. Otherwise, it add the string
        Args:
            code (str): ML code to check
        Returns:
            str: code formatted
    """
    if not code.replace(" ", "").startswith('model='):
        code+='model='
    return code

def exec_model(imports_code, model_code):
    """Runs the ML code and returns the generated model
        Args:
            imports_code (str): Imports before the code 
            model_code (str): ML code to run
        Returns:
            model: generated model from the code
    """

    if imports_code is not None and imports_code!='':
        """Checks if there is any import to be executed before the code"""
        exec (imports_code, None, globals())

    ml_code=format_ml_code(model_code)   
    exec (ml_code, None, globals())
    """Runs the ML code"""

    return model

def parse_kwargs_fit(kwargs_fit):
    """Converts kwargs_fit to a dictionary string
            kwargs_fit (str): Arguments for training.
            Example:
                epochs=5, steps_per_epoch=1000
        Returns:
            str: kwargs_fit formatted as string JSON
    """
    dic = {}
    kwargs_fit=kwargs_fit.replace(" ", "")
    for l in kwargs_fit.split(","):
        pair=l.split('=')
        dic[pair[0]]=int(pair[1])
    
    return json.dumps(dic)

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
            exec_model(imports_code, data['code'])
            model.summary()
            """Prints the information of the model"""

            serializer = MLModelSerializer(data=data)
            if serializer.is_valid():
                obj=serializer.save()
                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse("Information not valid", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(str(e))
            return HttpResponse('Model not valid', status=status.HTTP_400_BAD_REQUEST)

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
                    if data['code']!= model_obj.code:
                        try:
                            imports_code = '' if 'imports' not in data else data['imports']
                            exec_model(imports_code, data['code'])
                            """Execution of ML Mode"""
                        except Exception as e:
                            return HttpResponse('Model not valid: '+str(e), status=status.HTTP_400_BAD_REQUEST)
                    serializer.save()
                    return HttpResponse(status=status.HTTP_200_OK)
                else:
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)
    
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
        

class ConfigurationList(generics.ListCreateAPIView):
    """View to get the list of configurations and create a new configuration
        
        URL: /configurations
    """
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer

class ConfigurationID(generics.RetrieveUpdateDestroyAPIView):
    """View to get the information, update and delete a unique configuration. The configuration PK has be passed in the URL.
        
        URL: /configurations/{:configuration_pk}
    """
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer

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

class DeploymentList(generics.ListCreateAPIView):
    """View to get the list of deployments and create a new deployment in Kubernetes
        
        URL: /deployments
    """
    queryset = Deployment.objects.all()
    serializer_class = DeploymentSerializer

    def post(self, request, format=None):
        """ Expects a JSON in the request body with the information to create a new deployment

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
            serializer = DeployDeploymentSerializer(data=data)
            if serializer.is_valid():
                deployment = serializer.save()
                try:
                    """ KUBERNETES code goes here"""
                    config.load_incluster_config() # To run inside the container
                    #config.load_kube_config() # To run externally
                    api_instance = client.BatchV1Api()
        
                    for result in TrainingResult.objects.filter(deployment=deployment):
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
                                            'image': settings.TRAINING_MODEL_IMAGE, 
                                            'name': 'training',
                                            'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                    {'name': 'RESULT_URL', 'value': 'http://backend:8000/results/'+str(result.id)},
                                                    {'name': 'RESULT_ID', 'value': str(result.id)},
                                                    {'name': 'CONTROL_TOPIC', 'value': settings.CONTROL_TOPIC},
                                                    {'name': 'DEPLOYMENT_ID', 'value': str(deployment.id)},
                                                    {'name': 'BATCH', 'value': str(deployment.batch)},
                                                    {'name': 'KWARGS_FIT', 'value': parse_kwargs_fit(deployment.kwargs_fit)}],
                                        }],
                                        'imagePullPolicy': 'Never', # TODO: Remove this when the image is in DockerHub
                                        'restartPolicy': 'OnFailure'
                                    }
                                }
                            }
                        }
                        resp = api_instance.create_namespaced_job(body=job_manifest, namespace='default')
                    
                    return HttpResponse(status=status.HTTP_201_CREATED)
                except Exception as e:
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
            configuration= Configuration.objects.get(pk=pk)
            deployments = Deployment.objects.filter(configuration=configuration)
            serializer = DeploymentSerializer(deployments, many=True)
            return HttpResponse(json.dumps(serializer.data), status=status.HTTP_200_OK)
        else:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
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
            deployment= Deployment.objects.get(pk=pk)
            results = TrainingResult.objects.filter(deployment=deployment)
            serializer = TrainingResultSerializer(results, many=True)
            return HttpResponse(json.dumps(serializer.data), status=status.HTTP_200_OK)
        else:
            return HttpResponse('Deployment not found', status=status.HTTP_400_BAD_REQUEST)
        return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
    

class DownloadTrainedModel(generics.RetrieveAPIView):
    """View to download a trained model
        
        URL: GET /results/model/{:id_result} to get the model file trained.
    """
    def get(self, request, pk, format=None):
        try:
            result= TrainingResult.objects.get(pk=pk)  
            filename = path = os.path.join(settings.MEDIA_ROOT, result.trained_model.name)
            """Obtains the trained model filename"""

            with open(filename, 'rb') as f:
                file_data = f.read()
                response = HttpResponse(file_data, content_type='application/force-download')
                response['Content-Disposition'] = 'attachment; filename="model.h5"'
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
            result= TrainingResult.objects.get(pk=pk)
            filename = os.path.join(settings.MEDIA_ROOT, settings.MODELS_DIR)+str(result.model.id)+'.h5'
            """Obtains the model filename"""

            model = exec_model(result.model.imports, result.model.code)
            """Executes the model code"""
            
            model.save(filename)
            """Saves the model temporally"""

            with open(filename, 'rb') as f:
                file_data = f.read()
                f.close()
                response = HttpResponse(file_data, content_type='application/model')
                response['Content-Disposition'] = 'attachment; filename="model.h5"'
                result.status = TrainingResult.STATUS.deployed
                result.save()
                if os.path.exists(filename):
                    os.remove(filename)
                    """Removes the temporally file created"""
                return response
        except Exception as e:
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, pk, format=None):
        """ Expects a JSON in the request body with the information to upload the information of a result. 
            The result PK has to be in the URL.

            Args:
                pk (int): Primary key of the result (in the URL)
                trained_model (File): file with the trained model (body)
                json (str): Information to update the result (in the body).
                    train_loss_hist (str): List of trained losses
                    train_acc_hist (str): List of trained accuracies
                    val_loss (str): Loss in validation
                    val_acc (str): Accuracy in validation
                    
                    Request example:
                        FILES: trained_model: '...'   
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
                serializer = SimpleResultSerializer(obj, data = data, partial=True)
                
                if serializer.is_valid():
                    serializer.save()
                else:
                    return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

                trained_model = request.FILES['trained_model']
                fs = FileSystemStorage()
                path = os.path.join(settings.MEDIA_ROOT, settings.TRAINED_MODELS_DIR)
                if os.path.exists(path+str(obj.id)+'.h5'):
                    os.remove(path+str(obj.id)+'.h5')
                
                filename = fs.save(path+str(obj.id)+'.h5', trained_model)
                obj.trained_model.name=(settings.TRAINED_MODELS_DIR+str(obj.id)+'.h5')
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
                    config.load_incluster_config() # To run inside the container
                    #config.load_kube_config() # To run externally
                    api_instance = client.BatchV1Api()
                    api_response = api_instance.delete_namespaced_job(
                    name='model-training-'+str(result.id),
                    namespace="default",
                    body=client.V1DeleteOptions(
                        propagation_policy='Foreground',
                        grace_period_seconds=5))
                    result.status = 'stopped'
                    result.save()
                    return HttpResponse(status=status.HTTP_200_OK)
            return HttpResponse("Result not found or not running", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
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
                    config.load_incluster_config() # To run inside the container
                    #config.load_kube_config() # To run externally
                    api_instance = client.CoreV1Api()
                    api_response = api_instance.delete_namespaced_replication_controller(
                    name='model-inference-'+str(inference.id),
                    namespace="default",
                    body=client.V1DeleteOptions(
                        propagation_policy='Foreground',
                        grace_period_seconds=5))
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
        """ Checks the training result exists and returns the input format and configuration if there any in other inference or 
            datasource objects to facilitate the inference deployment.
        """
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
                datasources = Datasource.objects.filter(deployment=str(result.deployment.id))
                if datasources.count() > 0:
                    response['input_format']=datasources[0].input_format
                    response['input_config']=datasources[0].input_config # TODO change to input_config
            return HttpResponse(json.dumps(response), status=status.HTTP_200_OK)

        return HttpResponse('Result not found', status=status.HTTP_400_BAD_REQUEST)    

    def post(self, request, pk, format=None):
        """ Expects a JSON in the request body with the information to deploy a inference.
            The result PK has to be in the URL.

            Args:
                pk (int): Primary key of the result (in the URL)
                replicas (int): number of replicas to be deployed
                input_format (str): input format of the data received 
                configuration (str): configuration input format for the inference
                    Example:
                        {
                            "replicas": 2,
                            "input_format" : "RAW", 
                            "configuration" : {
                                "data_type": "uint8", 
                                "label_type": "uint8", 
                                "data_reshape": "28 28", 
                                "label_reshape": ""
                            }
                            "input_topic" : "inference-input",
                            "output_topic" : "inference-output",

                        }
                        
            Returns:
                HTTP_200_OK: if the inference has been deployed
                HTTP_400_BAD_REQUEST: if there has been any error deploying the inference
        """
        if TrainingResult.objects.filter(pk=pk).exists():
            try:
                data = json.loads(request.body)
                result = TrainingResult.objects.get(id=pk)
                serializer = DeployInferenceSerializer(data = data)
                
                if serializer.is_valid() and result.status == 'finished':
                    inference = serializer.save()
                    try:
                        config.load_incluster_config() # To run inside the container
                        #config.load_kube_config() # To run externally
                        api_instance = client.CoreV1Api()
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
                                            'image': settings.INFERENCE_MODEL_IMAGE, 
                                            'name': 'inference',
                                            'env': [{'name': 'BOOTSTRAP_SERVERS', 'value': settings.BOOTSTRAP_SERVERS},
                                                    {'name': 'MODEL_URL', 'value': 'http://backend:8000/results/model/'+str(result.id)},
                                                    {'name': 'INPUT_FORMAT', 'value': inference.input_format},
                                                    {'name': 'INPUT_CONFIG', 'value': inference.input_config},
                                                    {'name': 'INPUT_TOPIC', 'value': inference.input_topic},
                                                    {'name': 'OUTPUT_TOPIC', 'value': inference.output_topic},
                                                    {'name': 'GROUP_ID', 'value': 'inf'+str(result.id)}],
                                        }],
                                        'imagePullPolicy': 'Never' # TODO: Remove this when the image is in DockerHub
                                    }
                                }
                            }
                        }
                        resp = api_instance.create_namespaced_replication_controller(body=manifest, namespace='default') # create_namespaced_deployment
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
                """Checks data received is valid and the deployment received exists in the system"""
                
                producer = KafkaProducer(bootstrap_servers=settings.BOOTSTRAP_SERVERS)
                """Creates a Kafka Producer to send the message to the control topic"""
                
                kafka_data = copy.deepcopy(data)
                del kafka_data['deployment']
                del kafka_data['time']
                """Deletes unused attributes"""
                
                kafka_data['input_config'] = json.loads(kafka_data['input_config'])

                key = bytes([deployment_id])
                data_bytes = json.dumps(kafka_data).encode('utf-8')

                logging.info("Control message to be sent to kafka control topic %s", kafka_data)

                producer.send(settings.CONTROL_TOPIC, key=key, value=data_bytes)
                """Sends the data to Kafka"""
                producer.flush()
                """Waits until data is sent"""
                producer.close()
                """Closes the producer"""

                return HttpResponse(status=status.HTTP_201_CREATED)
            return HttpResponse('Deployment not valid', status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            logging.error(str(e))
            return HttpResponse(str(e), status=status.HTTP_400_BAD_REQUEST)