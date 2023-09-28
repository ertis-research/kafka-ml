from rest_framework import serializers
from automl.models import ModelSource, Datasource

class ModelSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelSource
        fields = ['federated_string_id', 'data_restriction', 'min_data', 'input_shape', 'output_shape', 'framework', 'time', 'distributed']


class DatasourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Datasource
        fields = ['topic', 'input_format', 'input_config', 'description', 'dataset_restrictions',
                'validation_rate', 'test_rate', 'total_msg', 'time']