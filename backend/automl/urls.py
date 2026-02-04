from django.urls import path

from automl.views.models import (
    ModelList,
    ModelID,
    DistributedModelList,
    FatherModelList,
    ModelResultID,
)
from automl.views.configurations import (
    ConfigurationList,
    ConfigurationID,
    ConfigurationUsedFrameworks,
    DistributedConfiguration,
)
from automl.views.deployments import (
    DeploymentList,
    DeploymentsConfigurationID,
    DeploymentResultID,
)
from automl.views.training_results import (
    TrainingResultList,
    TrainingResultID,
    TrainingResultStop,
    TrainingResultGetMetrics,
    TrainingResultMetricsID,
    DownloadTrainedModel,
    DownloadConfussionMatrix,
)

from automl.views.inferences import (
    InferenceList,
    InferenceResultID,
    InferenceStopDelete,
)

from automl.views.datasources import (
    DatasourceToKafka,
    DatasourceList
)

from automl.views.iot_devices import (
    IoTDeviceList,
    IoTDeviceID,
    IoTDeviceRetrieveModelView,
    IoTDeviceRetrieveScriptView,
    IotDeviceDeploy
)

urlpatterns = [
    path("configurations/", ConfigurationList.as_view()),
    path("configurations/<int:pk>", ConfigurationID.as_view()),
    path("frameworksInConfiguration/<int:pk>", ConfigurationUsedFrameworks.as_view()),
    path("distributedConfiguration/<int:pk>", DistributedConfiguration.as_view()),
    path("datasources/", DatasourceList.as_view()),
    path("datasources/kafka", DatasourceToKafka.as_view()),
    path("deployments/", DeploymentList.as_view()),
    path("deployments/<int:pk>", DeploymentsConfigurationID.as_view()),
    path("deployments/results/<int:pk>", DeploymentResultID.as_view()),
    path("inferences/", InferenceList.as_view()),
    path("inferences/<int:pk>", InferenceStopDelete.as_view()),
    path("models/", ModelList.as_view()),
    path("models/<int:pk>", ModelID.as_view()),
    path("models/result/<int:pk>", ModelResultID.as_view()),
    path("models/distributed", DistributedModelList.as_view()),
    path("models/fathers", FatherModelList.as_view()),
    path("results/", TrainingResultList.as_view()),
    path("results/<int:pk>", TrainingResultID.as_view()),
    path("results/stop/<int:pk>", TrainingResultStop.as_view()),
    path("results/inference/<int:pk>", InferenceResultID.as_view()),
    path("results/model/<int:pk>", DownloadTrainedModel.as_view()),
    path("results/confusion_matrix/<int:pk>", DownloadConfussionMatrix.as_view()),
    path("results/chart/<int:pk>", TrainingResultGetMetrics.as_view()),
    path("results_metrics/<int:pk>", TrainingResultMetricsID.as_view()),
    path("iot-devices/", IoTDeviceList.as_view()),
    path("iot-devices/<int:pk>", IoTDeviceID.as_view()),
    path("iot-devices/<str:token>/model.tflite", IoTDeviceRetrieveModelView.as_view()),
    path("iot-devices/<str:token>/autoexec.be", IoTDeviceRetrieveScriptView.as_view()),
    path("results/inference-iot/<int:pk>", IotDeviceDeploy.as_view()),
]
