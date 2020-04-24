from django.contrib import admin

# Register your models here.

from automl.models import MLModel, Configuration, Deployment, TrainingResult, Datasource, Inference


admin.site.register(MLModel)
admin.site.register(Configuration)
admin.site.register(Deployment)
admin.site.register(TrainingResult)
admin.site.register(Datasource)
admin.site.register(Inference)