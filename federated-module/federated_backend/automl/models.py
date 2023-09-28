from django.db import models
from django.utils.timezone import now
from django.conf import settings
from model_utils import Choices
from model_utils.fields import StatusField

class ModelSource(models.Model):
    """Machine learning model to be trained in the system"""
    federated_string_id = models.TextField()

    input_shape = models.TextField()
    output_shape = models.TextField()

    data_restriction = models.JSONField()
    min_data = models.IntegerField()

    framework = models.TextField(default='tf')
    distributed = models.BooleanField(default=False)

    time = models.DateTimeField(default=now, editable=False)

    class Meta(object):
        ordering = ('-time', )


class Datasource(models.Model):
    """Datasource used for training a deployed model"""

    INPUT_FORMAT = Choices('RAW', 'AVRO')
    """Sets its default value to the first item in the STATUS choices:"""
    input_format = StatusField(choices_name='INPUT_FORMAT')
    input_config = models.TextField(blank=True) 

    topic = models.TextField()

    total_msg = models.IntegerField(blank=True, null=True)
    validation_rate = models.DecimalField(max_digits=7, decimal_places=6, blank=True, null=True)
    test_rate = models.DecimalField(max_digits=7, decimal_places=6, blank=True, null=True)

    description = models.TextField(blank=True)
    dataset_restrictions = models.JSONField(default={}, blank=True, null=True)

    time = models.DateTimeField()

    class Meta(object):
        ordering = ('-time', )