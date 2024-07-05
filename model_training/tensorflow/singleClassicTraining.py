from mainTraining import *
from callbacks import *
import logging

class SingleClassicTraining(MainTraining):
    """Class for single models training
    
    Attributes:
        boostrap_servers (str): list of boostrap server for the Kafka connection
        result_url (str): URL for downloading the untrained model
        result_id (str): Result ID of the model
        control_topic(str): Control topic
        deployment_id (int): deployment ID of the application
        batch (int): Batch size used for training
        kwargs_fit (:obj:json): JSON with the arguments used for training
        kwargs_val (:obj:json): JSON with the arguments used for validation
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

    def get_models(self):
        """Downloads the model and loads it"""

        super().get_single_model()

    def get_data(self, kafka_topic, decoder):
        """Gets the data from Kafka"""

        return super().get_train_data(kafka_topic, self.result_id, decoder)
    
    def get_splits(self, data, kafka_dataset):
        """Gets the splits for training, validation and test"""
        
        return super().split_dataset(data, kafka_dataset)

    def train(self, splits, kafka_dataset, unsupervised_kafka_dataset, decoder, validation_rate, start):
        """Trains the model"""

        callback = SingleTrackTrainingCallback(NOT_DISTRIBUTED_NOT_INCREMENTAL, self.result_url, self.tensorflow_models)

        if unsupervised_kafka_dataset is None:
            return super().train_classic_model(splits, callback)
        else:
            return super().train_classic_semi_supervised_model(splits, unsupervised_kafka_dataset, callback)
    
    def saveMetrics(self, model_trained):
        """Saves the metrics of the model"""
        
        return super().saveSingleMetrics(model_trained)

    def test(self, splits, epoch_training_metrics, test_metrics):
        """Tests the model"""

        test = super().test_model(splits)

        for k, i in zip(epoch_training_metrics.keys(), range(len(epoch_training_metrics.keys()))):
            test_metrics[k] = [test[i]]
        
        return test_metrics

    def getConfussionMatrix(self, splits, training_results):
        """Gets the confussion matrix of the model"""

        return super().createConfussionMatrix(splits['test_dataset'], splits['test_size'])

    def sendMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
        """Sends the metrics to the control topic"""

        self.stream_timeout = None
        
        return super().sendSingleMetrics(cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix)