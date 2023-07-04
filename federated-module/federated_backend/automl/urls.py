from django.urls import path
from django.views.generic import TemplateView
from automl.views import DatasourceList, ModelFromControlLogger


urlpatterns = [
    path('federated-datasources/', DatasourceList.as_view()),
    path('model-control-logger/', ModelFromControlLogger.as_view())
]