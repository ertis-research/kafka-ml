from mainTraining import *
from callbacks import *

class DistributedFederatedTraining(MainTraining):
    """Class for distributed models federated training
    
    Attributes:
        boostrap_servers (str): list of boostrap server for the Kafka connection
        result_url (str): URL for downloading the untrained model
        result_id (str): Result ID of the model
        control_topic(str): Control topic
        deployment_id (int): deployment ID of the application
        batch (int): Batch size used for training
        kwargs_fit (:obj:json): JSON with the arguments used for training
        kwargs_val (:obj:json): JSON with the arguments used for validation
        optimizer (str): optimizer
        learning_rate (decimal): learning rate
        loss (str): loss
        metrics (str): monitoring metrics
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

        self.distributed = True
        self.incremental = False

        self.optimizer, self.learning_rate, self.loss, self.metrics = load_distributed_environment_vars()

        self.result_url = eval(self.result_url)
        self.result_id = eval(self.result_id)
        self.N = len(self.result_id)

        logging.info("Received distributed environment information (optimizer, learning_rate, loss, metrics) ([%s], [%s], [%s], [%s])",
                self.optimizer, str(self.learning_rate), self.loss, self.metrics)
        
        self.model_logger_topic, self.federated_string_id, self.agg_rounds, self.data_restriction, self.min_data, self.agg_strategy = load_federated_environment_vars()

        logging.info("Received federated environment information (model_logger_topic, federated_string_id, agg_rounds, data_restriction, min_data, agg_strategy) ([%s], [%s], [%d], [%s], [%d], [%s])",
                self.model_logger_topic, self.federated_string_id, self.agg_rounds, self.data_restriction, self.min_data, self.agg_strategy)

    def get_models(self):
        """Downloads the models and loads them"""

        super().get_distributed_models()
    
    def configure_distributed_models(self):
        """Configures the distributed models"""

        super().create_distributed_model()
    
    def generate_and_send_data_standardization(self):
        """Generates and sends the data standardization"""
        
        super().generate_and_send_data_standardization(self.model_logger_topic, self.federated_string_id, self.data_restriction, self.min_data, self.distributed, self.incremental)

    def generate_federated_kafka_topics(self):
        """Generates the Kafka topics for the federated training"""

        super().generate_federated_kafka_topics()
    
    def parse_metrics(self, model_metrics):
        """Parse the metrics from the model"""

        return super().parse_distributed_metrics(model_metrics)

    def sendTempMetrics(self, train_metrics, val_metrics):
        """Send the metrics to the backend"""
        
        super().sendDistributedTempMetrics(train_metrics, val_metrics)
    
    def sendFinalMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
        """Sends the metrics to the control topic"""
        
        self.stream_timeout = None

        return super().sendDistributedMetrics(epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime)