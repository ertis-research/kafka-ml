from django.contrib import admin

from automl.models import Datasource, ModelSource

admin.site.register(ModelSource)
admin.site.register(Datasource)
