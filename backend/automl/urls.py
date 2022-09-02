from django.urls import path
from django.views.generic import TemplateView
from automl.views import ModelList, ModelID, DeploymentList, TrainingResultID, ConfigurationList, ConfigurationID, DatasourceToKafka, ConfigurationUsedFrameworks, DistributedConfiguration
from automl.views import DeploymentsConfigurationID, TrainingResultList, DeploymentResultID, DownloadTrainedModel, DatasourceList, TrainingResultGetMetrics, DownloadConfussionMatrix
from automl.views import InferenceResultID, InferenceList, InferenceStopDelete, TrainingResultStop, DistributedModelList, FatherModelList, ModelResultID, TrainingResultMetricsID

urlpatterns = [
    path('configurations/', ConfigurationList.as_view()),
    path('configurations/<int:pk>', ConfigurationID.as_view()),
    path('frameworksInConfiguration/<int:pk>', ConfigurationUsedFrameworks.as_view()),
    path('distributedConfiguration/<int:pk>', DistributedConfiguration.as_view()),
    path('datasources/', DatasourceList.as_view()),
    path('datasources/kafka', DatasourceToKafka.as_view()),
    path('deployments/', DeploymentList.as_view()),
    path('deployments/<int:pk>', DeploymentsConfigurationID.as_view()),
    path('deployments/results/<int:pk>', DeploymentResultID.as_view()), 
    path('inferences/', InferenceList.as_view()),
    path('inferences/<int:pk>', InferenceStopDelete.as_view()), 
    path('models/', ModelList.as_view()),
    path('models/<int:pk>', ModelID.as_view()),
    path('models/result/<int:pk>', ModelResultID.as_view()),
    path('models/distributed', DistributedModelList.as_view()),
    path('models/fathers', FatherModelList.as_view()),
    path('results/', TrainingResultList.as_view()),
    path('results/<int:pk>', TrainingResultID.as_view()),
    path('results/stop/<int:pk>', TrainingResultStop.as_view()),
    path('results/inference/<int:pk>', InferenceResultID.as_view()),
    path('results/model/<int:pk>', DownloadTrainedModel.as_view()),
    path('results/confusion_matrix/<int:pk>', DownloadConfussionMatrix.as_view()),
    path('results/chart/<int:pk>', TrainingResultGetMetrics.as_view()),
    path('results_metrics/<int:pk>', TrainingResultMetricsID.as_view()),
]