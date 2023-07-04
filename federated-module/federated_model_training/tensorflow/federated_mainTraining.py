from utils import *
import json
import tensorflow_io.kafka as kafka_io
import traceback
import requests
import random, string, time
from KafkaModelEngine import KafkaModelEngine

from decoders import *

class MainTraining(object):
    """Main class for training
    
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

        self.kml_cloud_bootstrap_server = os.environ.get('KML_CLOUD_BOOTSTRAP_SERVERS')
        self.data_bootstrap_server = os.environ.get('DATA_BOOTSTRAP_SERVERS')

        self.federated_model_id = os.environ.get('FEDERATED_MODEL_ID')

        self.input_data_topic = os.environ.get('DATA_TOPIC')
        self.input_format = os.environ.get('INPUT_FORMAT')
        self.input_config = json.loads(os.environ.get('INPUT_CONFIG'))

        self.validation_rate = float(os.environ.get('VALIDATION_RATE'))
        self.total_msg = int(os.environ.get('TOTAL_MSG'))

        logging.info("Received main environment information (KML_CLOUD_BOOTSTRAP_SERVERS, DATA_BOOTSTRAP_SERVERS, FEDERATED_MODEL_ID, DATA_TOPIC, INPUT_FORMAT, INPUT_CONFIG, VALIDATION_RATE, TOTAL_MSG) ([%s], [%s], [%s], [%s], [%s], [%s], [%f], [%d])",
                        self.kml_cloud_bootstrap_server, self.data_bootstrap_server, self.federated_model_id, self.input_data_topic, self.input_format, self.input_config, self.validation_rate, self.total_msg)

        # Syntetic data        
        self.training_size = int((1-(float(self.validation_rate)))*(int(self.total_msg)))
        self.kafka_dataset = None

        # Create Kafka-related variables
        self.model_control_topic = f'FED-{self.federated_model_id}-model_control_topic'
        self.model_data_topic = f'FED-{self.federated_model_id}-model_data_topic'
        self.aggregation_control_topic = f'FED-{self.federated_model_id}-agg_control_topic'
        self.aggregation_data_topic = f'FED-{self.federated_model_id}-agg_data_topic'
        self.group_id = 'federated-'+self.federated_model_id+'-'.join(random.choice(string.ascii_lowercase) for _ in range(5))



    def get_kafka_dataset(self, training_settings):
        logging.info("Fetching dataset from Kafka Topic [%s], with bootstrap server [%s]", self.input_data_topic, self.data_bootstrap_server)  

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        self.kafka_dataset = kafka_io.KafkaDataset(self.input_data_topic, servers=self.data_bootstrap_server, group=self.group_id, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))
        self.train_dataset = self.kafka_dataset.take(self.training_size).batch(training_settings['batch'])
        self.validation_dataset = self.kafka_dataset.skip(self.training_size).batch(training_settings['batch'])

        logging.info("Dataset fetched successfully")

    def load_model(self, message):
        model_reader = KafkaModelEngine(self.kml_cloud_bootstrap_server, self.group_id)  
        model = model_reader.getModel(message)

        return model
     
    
    def train_classic_model(self, model, training_settings):
        """Trains classic model"""

        start = time.time()
        model_trained = model.fit(self.train_dataset, validation_data=self.validation_dataset, **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))
        
        return model_trained
    
    def save_metrics(self, model_trained):
        """Saves the metrics of single models"""

        epoch_training_metrics = {}
        epoch_validation_metrics = {}

        for k, v in model_trained.history.items():
            if not k.startswith("val_"):
                try:
                    epoch_training_metrics[k].append(v)
                except:
                    epoch_training_metrics[k] = v
            else:
                try:
                    epoch_validation_metrics[k[4:]].append(v)
                except:
                    epoch_validation_metrics[k[4:]] = v
        
        return epoch_training_metrics, epoch_validation_metrics