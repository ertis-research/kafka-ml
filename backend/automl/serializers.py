from rest_framework import serializers
from automl.models import MLModel, Configuration, Deployment, TrainingResult, Datasource, Inference

class SimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModel
        fields = ['id', 'name']

class MLModelSerializer(serializers.ModelSerializer):
    father = SimpleModelSerializer(read_only=True, required=False)
    class Meta:
        model = MLModel
        fields = ['id', 'code', 'name', 'description', 'imports', 'distributed', 'father', 'framework']

    def update(self, instance, validated_data):
        father = self.initial_data.get("father") if "father" in self.initial_data else None

        for (key, value) in validated_data.items():
            setattr(instance, key, value)
        
        if instance.distributed:
            if father:
                if father == instance.id:
                    raise serializers.ValidationError("A model can not be its own father")
                else:
                    instance.father = MLModel.objects.get(pk=father)
        else:
            instance.father = None

        instance.save()
        
        return instance

    def create(self, validated_data):
        father = self.initial_data.get("father") if "father" in self.initial_data else None
        model = MLModel.objects.create(**validated_data)
        if model.distributed:
            if father:
                model.father = MLModel.objects.get(pk=father)
        else:
            model.father = None

        model.save()
        return model

class SimpleDeploymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deployment
        fields = ['id','time']
        
class ConfigurationSerializer(serializers.ModelSerializer):
    ml_models = SimpleModelSerializer(many=True, read_only=True)
    deployments = SimpleDeploymentSerializer(many=True, read_only=True)
    class Meta:
        model = Configuration
        fields = ['id', 'name', 'description', 'ml_models', 'deployments']
    

    def update(self, instance, validated_data):
        ml_models = self.initial_data.get("ml_models") if "ml_models" in self.initial_data else []

        for (key, value) in validated_data.items():
            setattr(instance, key, value)

        for existing_model in instance.ml_models.all():
            """Delete existing relations"""
            instance.ml_models.remove(existing_model)
        
        for model in ml_models:
            """Add new relations"""
            instance.ml_models.add(MLModel.objects.get(pk=model))
        
        instance.save()
        
        return instance

    def create(self, validated_data):
        ml_models = self.initial_data.get("ml_models") if "ml_models" in self.initial_data else []
        configuration = Configuration.objects.create(**validated_data)
        for model in ml_models:
            configuration.ml_models.add(MLModel.objects.get(pk=model))
        return configuration

class SimpleConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = ['id', 'name']

class SimpleTrainingResultSerializer(serializers.ModelSerializer):    
    model = SimpleModelSerializer()

    class Meta:
        model = TrainingResult
        fields = ['id', 'status', 'model', 'status_changed']

class DeployDeploymentSerializer(serializers.ModelSerializer):
    configuration = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Deployment
        fields = ['optimizer', 'learning_rate', 'loss', 'metrics']+[
                'incremental', 'indefinite', 'stream_timeout', 'monitoring_metric', 'change', 'improvement']+[
                'unsupervised', 'unsupervised_rounds', 'confidence']+[
                'batch', 'tf_kwargs_fit', 'tf_kwargs_val', 'pth_kwargs_fit', 'pth_kwargs_val', 'conf_mat_settings', 'configuration']+[
                'federated', 'agg_rounds', 'min_data', 'agg_strategy', 'data_restriction']
    
    def validate_batch(self, value):
        """Checks that batch size is greater than 0"""
        
        if value <= 0:
            raise serializers.ValidationError("Batch has to be greater than 0")
        return value
    
    def validate_kwargs_fit(self, value):
        """Checks that arguments for training have the expected format"""
        import re
        if not bool(re.match('^[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*(,[ ]*[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*)*$', value)):
            raise serializers.ValidationError("Arguments for training do not have the expected format")
        return value

    def validate_kwargs_val(self, value):
        """Checks that arguments for training have the expected format"""
        import re
        if not bool(re.match('^[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*(,[ ]*[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*)*$', value)):
            raise serializers.ValidationError("Arguments for training do not have the expected format")
        return value

    def create(self, validated_data):
        """Creates a new deployment, associated it with the configuration and creates related results"""

        configuration_id = self.initial_data.get("configuration") if "configuration" in self.initial_data else ''
        configuration = Configuration.objects.get(pk=configuration_id)
        deployment = Deployment.objects.create(configuration=configuration, **validated_data)
        for model in configuration.ml_models.all():
            TrainingResult.objects.create(model=model, deployment=deployment)
        return deployment

class DeploymentSerializer(serializers.ModelSerializer):
    configuration = SimpleConfigurationSerializer()
    results = SimpleTrainingResultSerializer(many=True, read_only=True)

    class Meta:
        model = Deployment
        fields = ['id', 'configuration', 'results']+[
                'optimizer', 'learning_rate', 'loss', 'metrics']+[
                'incremental', 'indefinite', 'stream_timeout', 'monitoring_metric', 'change', 'improvement']+[
                'unsupervised', 'unsupervised_rounds', 'confidence']+[
                'batch', 'tf_kwargs_fit', 'tf_kwargs_val', 'pth_kwargs_fit', 'pth_kwargs_val', 'conf_mat_settings', 'time']+[
                'federated', 'agg_rounds', 'min_data', 'agg_strategy', 'data_restriction']

class RoundingDecimalField(serializers.DecimalField):
    """Used to automatically round decimals to the model's accepted value."""

    def validate_precision(self, value):
        return value

class SimpleResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingResult
        fields = ['id', 'train_metrics', 'val_metrics', 'test_metrics', 'confusion_matrix', 'training_time']

class SimplerResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingResult
        fields = ['id', 'train_metrics', 'val_metrics']

class TrainingResultSerializer(serializers.ModelSerializer):
    deployment = SimpleDeploymentSerializer()
    model = SimpleModelSerializer()
    
    class Meta:
        model = TrainingResult
        fields = ['id', 'status', 'status_changed', 'deployment', 
                'model', 'train_metrics', 'val_metrics', 'test_metrics', 'confusion_matrix', 'training_time']

class DatasourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Datasource
        fields = ['input_format', 'deployment', 'input_config',
        'description', 'topic', 'validation_rate', 'test_rate', 'total_msg', 'time']

class DeployInferenceSerializer(serializers.ModelSerializer):
    model_result = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Inference
        fields = ['model_result', 'replicas', 'input_format', 'input_config', 'input_topic', 'output_topic', 'limit', 'output_upper', 'token', 'external_host', 'input_kafka_broker' , 'output_kafka_broker', 'upper_kafka_broker']

    def create(self, validated_data):
        """Creates a new inference, associated it with the result"""

        result_id = self.initial_data.get("model_result") if "model_result" in self.initial_data else ''
        result = TrainingResult.objects.get(pk=result_id)
        inference = Inference.objects.create(model_result=result, **validated_data)
        return inference


class InferenceSerializer(serializers.ModelSerializer):
    model_result = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Inference
        fields = ['id', 'model_result', 'replicas', 'input_format', 'input_config', 'input_topic', 'output_topic', 'time', 'status', 'status_changed', 'limit', 'output_upper', 'token', 'external_host', 'input_kafka_broker' , 'output_kafka_broker', 'upper_kafka_broker']