from django.urls import path
from django.views.generic import TemplateView
from automl.views import ModelList, ModelID, DeploymentList, TraningResultID, ConfigurationList, ConfigurationID, DatasourceToKafka
from automl.views import DeploymentsConfigurationID, TrainingResultList, DeploymentResultID, DownloadTrainedModel, DatasourceList
from automl.views import InferenceResultID

urlpatterns = [
    path('configurations/', ConfigurationList.as_view()),
    path('configurations/<int:pk>', ConfigurationID.as_view()),
    path('datasources/', DatasourceList.as_view()),
    path('datasources/kafka', DatasourceToKafka.as_view()),
    path('deployments/', DeploymentList.as_view()),
    path('deployments/<int:pk>', DeploymentsConfigurationID.as_view()),
    path('deployments/results/<int:pk>', DeploymentResultID.as_view()),
    path('models/', ModelList.as_view()),
    path('models/<int:pk>', ModelID.as_view()),
    path('results/', TrainingResultList.as_view()),
    path('results/<int:pk>', TraningResultID.as_view()),
    path('results/inference/<int:pk>', InferenceResultID.as_view()),
    path('results/model/<int:pk>', DownloadTrainedModel.as_view()),
]