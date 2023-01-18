from mainTraining import *
from callbacks import *

class DistributedIncrementalTraining(MainTraining):
    """Class for distributed models incremental training
    
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
        stream_timeout (int): stream timeout to wait for new data
        message_poll_timeout (int): window size to get new data
        monitoring_metric (str): metric to track for indefinite training
        change (str): direction in which monitoring metric improves
        improvement (decimal): how many the monitoring metric improves
        numeratorBatch (int): number of batches to take for validation
        denominatorBatch (int): total number of batches for validation
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

        self.optimizer, self.learning_rate, self.loss, self.metrics = load_distributed_environment_vars()

        self.result_url = eval(self.result_url)
        self.result_id = eval(self.result_id)
        self.N = len(self.result_id)

        logging.info("Received distributed environment information (optimizer, learning_rate, loss, metrics) ([%s], [%s], [%s], [%s])",
                self.optimizer, str(self.learning_rate), self.loss, self.metrics)

        self.stream_timeout, self.message_poll_timeout, self.monitoring_metric, self.change, self.improvement, self.numeratorBatch, self.denominatorBatch = load_incremental_environment_vars()

        if self.stream_timeout == -1:
            self.monitoring_metric = 'loss'
            self.change = 'down'

        logging.info("Received incremental environment information (stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch) ([%d], [%d], [%s], [%s], [%s], [%d], [%d])",
                self.stream_timeout, self.message_poll_timeout, self.monitoring_metric, self.change, str(self.improvement), self.numeratorBatch, self.denominatorBatch)

    def get_models(self):
        """Downloads the models and loads them"""

        super().get_distributed_models()

    def get_data(self, kafka_topic, decoder):
        """Gets the incremental data from Kafka"""

        return super().get_online_train_data(kafka_topic)
    
    def configure_distributed_models(self):
        """Configures the distributed models"""

        super().create_distributed_model()
    
    def train(self, splits, kafka_dataset, decoder, start):
        """Trains the model"""

        callback = DistributedTrackTrainingCallback(DISTRIBUTED_INCREMENTAL, self.result_url, self.tensorflow_models)

        return super().train_incremental_model(kafka_dataset, decoder, callback, start)
    
    def saveMetrics(self, model_trained, incremental_validation):
        """Saves the metrics of the model"""
        
        epoch_training_metrics = []
        epoch_validation_metrics = []

        for m in self.tensorflow_models:
            train_dic = {}
            for k, v in model_trained.history.items():
                if m.name in k:
                    try:
                        train_dic[k[len(m.name)+1:]].append(v)
                    except:
                        train_dic[k[len(m.name)+1:]] = v
            epoch_training_metrics.append(train_dic)
        if incremental_validation != {}:
            incremental_validation.pop('loss')
            for m in self.tensorflow_models:
                val_dic = {}
                for k in incremental_validation.keys():
                    if m.name in k:
                        val_dic[k[len(m.name)+1:]] = incremental_validation[k]
                epoch_validation_metrics.append(val_dic)
        else:
            epoch_validation_metrics.append({})

        return epoch_training_metrics, epoch_validation_metrics, []
    
    def sendMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
        """Sends the metrics to the control topic"""

        return super().sendDistributedMetrics(epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime)