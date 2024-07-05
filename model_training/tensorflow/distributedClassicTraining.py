from mainTraining import *
from callbacks import *

class DistributedClassicTraining(MainTraining):
    """Class for distributed models training
    
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

        self.optimizer, self.learning_rate, self.loss, self.metrics = load_distributed_environment_vars()

        self.result_url = eval(self.result_url)
        self.result_id = eval(self.result_id)
        self.N = len(self.result_id)

        logging.info("Received distributed environment information (optimizer, learning_rate, loss, metrics) ([%s], [%s], [%s], [%s])",
                self.optimizer, str(self.learning_rate), self.loss, self.metrics)

    def get_models(self):
        """Downloads the models and loads them"""

        super().get_distributed_models()

    def get_data(self, kafka_topic, decoder):
        """Gets the data from Kafka"""

        return super().get_train_data(kafka_topic, str(self.result_id), decoder)
    
    def get_splits(self, data, kafka_dataset):
        """Gets the splits for training, validation and test"""
        
        return super().split_dataset(data, kafka_dataset)

    def configure_distributed_models(self):
        """Configures the distributed models"""

        super().create_distributed_model()
    
    def train(self, splits, kafka_dataset, unsupervised_kafka_dataset, decoder, validation_rate, start):
        """Trains the model"""

        callback = DistributedTrackTrainingCallback(DISTRIBUTED_NOT_INCREMENTAL, self.result_url, self.tensorflow_models)

        if unsupervised_kafka_dataset is None:
            return super().train_classic_model(splits, callback)
        else:
            return super().train_classic_semi_supervised_model(splits, unsupervised_kafka_dataset, callback)
    
    def saveMetrics(self, model_trained):
        """Saves the metrics of the model"""
        
        return super().saveDistributedMetrics(model_trained)
    
    def test(self, splits, epoch_training_metrics, test_metrics):
        """Tests the model"""

        test = super().test_model(splits)

        for x in range(self.N):
            test_dic = {}
            for k, i in zip(epoch_training_metrics[x].keys(), range(x+1, len(epoch_training_metrics[x].keys())*self.N+1, self.N)):
                test_dic[k] = [test[i]]
            test_metrics.append(test_dic)
        
        return test_metrics
    
    def sendMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
        """Sends the metrics to the control topic"""

        self.stream_timeout = None
        
        return super().sendDistributedMetrics(epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime)