from federated_mainTraining import MainTraining

class SingleIncrementalTraining(MainTraining):
    """Class for single models incremental training
    
    Attributes:
        kml_cloud_bootstrap_server (str): Kafka bootstrap server for the KML Cloud
        data_bootstrap_server (str): Kafka bootstrap server for data
        federated_model_id (str): Federated model ID
        input_data_topic (str): Input data topic
        input_format (str): Input data format
        input_config (dict): Input data configuration
        validation_rate (float): Validation rate
        total_msg (int): Total number of messages
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

    def get_data(self, training_settings):
        """Gets the data from Kafka"""

        return super().get_online_kafka_dataset(training_settings)

    def load_model(self, message):
        """Downloads the model and loads it"""

        return super().load_model(message)
    
    def train(self, model, training_settings):
        """Trains the model"""
        
        return super().train_incremental_model(model, training_settings)
    
    def save_metrics(self, model_trained):
        """Saves the metrics of the model"""
        
        return super().save_metrics(model_trained)