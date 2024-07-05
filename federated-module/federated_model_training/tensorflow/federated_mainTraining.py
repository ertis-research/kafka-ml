from utils import *
import json
import time

import tensorflow_io as tfio
import tensorflow_io.kafka as kafka_io
from confluent_kafka.admin import AdminClient, NewTopic

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
        self.federated_client_id = os.environ.get('FEDERATED_CLIENT_ID')

        self.input_data_topic = os.environ.get('DATA_TOPIC')
        self.unsupervised_data_topic = os.environ.get('UNSUPERVISED_TOPIC')
        self.input_format = os.environ.get('INPUT_FORMAT')
        self.input_config = json.loads(os.environ.get('INPUT_CONFIG'))

        self.validation_rate = float(os.environ.get('VALIDATION_RATE'))
        self.total_msg = -1 if os.environ.get('TOTAL_MSG') == 'None' else int(os.environ.get('TOTAL_MSG'))

        logging.info("Received main environment information (KML_CLOUD_BOOTSTRAP_SERVERS, DATA_BOOTSTRAP_SERVERS, FEDERATED_MODEL_ID, DATA_TOPIC, INPUT_FORMAT, INPUT_CONFIG, VALIDATION_RATE, TOTAL_MSG) ([%s], [%s], [%s], [%s], [%s], [%s], [%f], [%d])",
                        self.kml_cloud_bootstrap_server, self.data_bootstrap_server, self.federated_model_id, self.input_data_topic, self.input_format, self.input_config, self.validation_rate, self.total_msg)

        # Syntetic data
        if self.total_msg != -1:
            self.training_size = int((1-(float(self.validation_rate)))*(int(self.total_msg)))
        self.kafka_dataset = None
        if self.unsupervised_data_topic is not None:
            self.unsupervised_kafka_dataset = None

        self.model_trained = None

        # Create Kafka-related variables
        self.model_control_topic = f'FED-{self.federated_model_id}-model_control_topic'
        self.model_data_topic = f'FED-{self.federated_model_id}-model_data_topic'
        self.aggregation_control_topic = f'FED-{self.federated_model_id}-agg_control_topic'
        self.aggregation_data_topic = f'FED-{self.federated_model_id}-agg_data_topic-{self.federated_client_id}'
        self.group_id = f'FED-MODEL-{self.federated_model_id}-CLIENT-{self.federated_client_id}'

        # Set up the admin client
        admin_client = AdminClient({'bootstrap.servers': self.kml_cloud_bootstrap_server})

        topics_to_create = []
        topics_to_create.append(NewTopic(self.aggregation_data_topic, 1, config={'max.message.bytes': '10000000'}))   # 10 MB

        admin_client.create_topics(topics_to_create)

        # Wait for the topic to be created
        topic_created = False
        while not topic_created:
            topic_metadata = admin_client.list_topics(timeout=-1)
            if self.aggregation_data_topic in topic_metadata.topics: 
                topic_created = True

    def get_kafka_dataset(self, training_settings):
        logging.info("Fetching labeled dataset from Kafka Topic [%s], with bootstrap server [%s]", self.input_data_topic, self.data_bootstrap_server)  

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        self.kafka_dataset = kafka_io.KafkaDataset(self.input_data_topic, servers=self.data_bootstrap_server, group=self.group_id, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))
        self.train_dataset = self.kafka_dataset.take(self.training_size).batch(training_settings['batch'])
        self.validation_dataset = self.kafka_dataset.skip(self.training_size).batch(training_settings['batch'])

        logging.info("Dataset fetched successfully")
    
    def get_unsupervised_kafka_dataset(self, training_settings):
        logging.info("Fetching unlabeled dataset from Kafka Topic [%s], with bootstrap server [%s]", self.unsupervised_data_topic, self.data_bootstrap_server)  

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        self.unsupervised_kafka_dataset = kafka_io.KafkaDataset(self.unsupervised_data_topic, servers=self.data_bootstrap_server, group=self.group_id, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y)).batch(training_settings['batch'])

        logging.info("Unlabeled dataset fetched successfully")

    def get_online_kafka_dataset(self, training_settings):
        logging.info("Fetching online dataset from Kafka Topic [%s], with bootstrap server [%s]", self.input_data_topic, self.data_bootstrap_server)  

        self.kafka_dataset = tfio.experimental.streaming.KafkaBatchIODataset(topics=[self.input_data_topic], servers=self.data_bootstrap_server, group_id=self.group_id+'-2', stream_timeout=training_settings['stream_timeout'], configuration=None, internal=True)

        logging.info("Dataset fetched successfully")

    def get_online_unsupervised_kafka_dataset(self, training_settings):
        logging.info("Fetching unlabeled online dataset from Kafka Topic [%s], with bootstrap server [%s]", self.unsupervised_data_topic, self.data_bootstrap_server)  

        self.unsupervised_kafka_dataset = tfio.experimental.streaming.KafkaBatchIODataset(topics=[self.unsupervised_data_topic], servers=self.data_bootstrap_server, group_id=self.group_id+'-2', stream_timeout=training_settings['stream_timeout'], configuration=None, internal=True)

        logging.info("Unlabeled dataset fetched successfully")
    
    def split_online_dataset(self, kafka_dataset):
        """Splits the online dataset for training and validation"""

        training_size = int((1-self.validation_rate)*len(kafka_dataset))
        validation_size = int(self.validation_rate*len(kafka_dataset))
        logging.info("Training batch size %d and validation batch size %d", training_size, validation_size)

        train_dataset = kafka_dataset.take(training_size)
        """Splits dataset for training"""

        if validation_size > 0:
            validation_dataset = kafka_dataset.skip(training_size)
        else:
            """If no validation is greater than 0, then split the dataset for training"""
            validation_dataset = None

        splits = {
            'train_dataset': train_dataset,
            'validation_dataset': validation_dataset
        }

        return splits
    
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
    
    def train_classic_semi_supervised_model(self, model, training_settings):
        """Trains semi-supervised model"""

        x_train = np.concatenate([x for x, y in self.train_dataset], axis=0)
        y_train = np.concatenate([y for x, y in self.train_dataset], axis=0)

        x_val = np.concatenate([x for x, y in self.validation_dataset], axis=0)
        y_val = np.concatenate([y for x, y in self.validation_dataset], axis=0)

        logging.info("Training model with labeled data")

        start = time.time()

        if 'N' not in training_settings:
            model_trained = model.fit(x=x_train, y=y_train, validation_data=(x_val, y_val), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
        else:
            y_training = []
            y_validation = []
            for i in range(training_settings['N']):
                y_training.append(y_train)
                y_validation.append(y_val)
            model_trained = model.fit(x=x_train, y=y_training, validation_data=(x_val, y_validation), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])

        x_unlabeled = np.concatenate([x for x, y in self.unsupervised_kafka_dataset], axis=0)

        for round in range(training_settings['unsupervised_rounds']):
            if len(x_unlabeled) > 0:
                predictions = model.predict(x_unlabeled)
                
                if 'N' not in training_settings:
                    confidence_scores = np.max(predictions, axis=1)
                    pseudo_labels = np.argmax(predictions, axis=1)
                else:
                    confidence_scores = np.max(predictions[-1], axis=1)
                    pseudo_labels = np.argmax(predictions[-1], axis=1)

                high_confidence_indices = confidence_scores >= training_settings['confidence']
                high_confidence_pseudo_labels = pseudo_labels[high_confidence_indices]
                high_confidence_unlabeled_data = x_unlabeled[high_confidence_indices]

                if len(high_confidence_pseudo_labels) == 0:
                    logging.info("No high-confidence pseudo-labels found. Stopping.")
                    break
                else:
                    logging.info("Round %d: Found %d high-confidence pseudo-labels", round, len(high_confidence_pseudo_labels))

                high_confidence_pseudo_labels = np.expand_dims(high_confidence_pseudo_labels, axis=1)

                x_combined = np.concatenate([x_train, high_confidence_unlabeled_data])
                y_combined = np.concatenate([y_train, high_confidence_pseudo_labels])

                logging.info("Training model with labeled and pseudo-labeled data")

                if 'N' not in training_settings:
                    unsupervised_model_trained = model.fit(x_combined, y_combined, validation_data=(x_val, y_val), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
                else:
                    y_training = []
                    for i in range(training_settings['N']):
                        y_training.append(y_combined)
                    unsupervised_model_trained = model.fit(x_combined, y_training, validation_data=(x_val, y_validation), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])

                x_train = x_combined
                y_train = y_combined

                x_unlabeled = np.delete(x_unlabeled, high_confidence_indices, axis=0)

                for key in model_trained.history.keys():
                    model_trained.history[key].extend(unsupervised_model_trained.history[key])
            else:
                logging.info("No more unlabeled data. Stopping.")
                break
        
        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))

        return model_trained
    
    def train_incremental_model(self, model, training_settings):
        """Trains incremental model"""

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)

        start = time.time()

        while 'model_trained' not in locals() and 'model_trained' not in globals():
            for mini_ds in self.kafka_dataset:
                if len(mini_ds) > 0:
                    mini_ds = mini_ds.map(lambda x, y: decoder.decode(x, y))
                    splits = self.split_online_dataset(mini_ds)
                    splits['train_dataset'] = splits['train_dataset'].batch(training_settings['batch'])
                    if splits['validation_dataset'] is not None:
                        splits['validation_dataset'] = splits['validation_dataset'].batch(training_settings['batch'])
                    model_trained = model.fit(splits['train_dataset'], validation_data=splits['validation_dataset'], **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
        
        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))
        
        return model_trained
    
    def train_incremental_semi_supervised_model(self, model, training_settings):
        """Trains incremental semi-supervised model"""

        x_train = np.concatenate([x for x, y in self.train_dataset], axis=0)
        y_train = np.concatenate([y for x, y in self.train_dataset], axis=0)

        x_val = np.concatenate([x for x, y in self.validation_dataset], axis=0)
        y_val = np.concatenate([y for x, y in self.validation_dataset], axis=0)

        start = time.time()
        
        if self.model_trained is None:
            logging.info("Training model with labeled data")
            if 'N' not in training_settings:
                self.model_trained = model.fit(x=x_train, y=y_train, validation_data=(x_val, y_val), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
            else:
                y_training = []
                y_validation = []
                for i in range(training_settings['N']):
                    y_training.append(y_train)
                    y_validation.append(y_val)
                self.model_trained = model.fit(x=x_train, y=y_training, validation_data=(x_val, y_validation), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)

        for unsupervised_mini_ds in self.unsupervised_kafka_dataset:
            if len(unsupervised_mini_ds) > 0:
                unsupervised_mini_ds = unsupervised_mini_ds.map(lambda x, y: decoder.decode(x, y)).batch(training_settings['batch'])
                x_unlabeled = np.concatenate([x for x, y in unsupervised_mini_ds], axis=0)

                predictions = model.predict(x_unlabeled)
                
                if 'N' not in training_settings:
                    confidence_scores = np.max(predictions, axis=1)
                    pseudo_labels = np.argmax(predictions, axis=1)
                else:
                    confidence_scores = np.max(predictions[-1], axis=1)
                    pseudo_labels = np.argmax(predictions[-1], axis=1)

                high_confidence_indices = confidence_scores >= training_settings['confidence']
                high_confidence_pseudo_labels = pseudo_labels[high_confidence_indices]
                high_confidence_unlabeled_data = x_unlabeled[high_confidence_indices]

                if len(high_confidence_pseudo_labels) == 0:
                    logging.info("No high-confidence pseudo-labels found. Stopping.")
                    break
                else:
                    logging.info("Found %d high-confidence pseudo-labels", len(high_confidence_pseudo_labels))

                high_confidence_pseudo_labels = np.expand_dims(high_confidence_pseudo_labels, axis=1)

                x_combined = np.concatenate([x_train, high_confidence_unlabeled_data])
                y_combined = np.concatenate([y_train, high_confidence_pseudo_labels])

                logging.info("Training model with labeled and pseudo-labeled data")
                
                if 'N' not in training_settings:
                    unsupervised_model_trained = model.fit(x_combined, y_combined, validation_data=(x_val, y_val), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
                else:
                    y_training = []
                    y_validation = []
                    for i in range(training_settings['N']):
                        y_training.append(y_combined)
                        y_validation.append(y_val)
                    unsupervised_model_trained = model.fit(x_combined, y_training, validation_data=(x_val, y_validation), **training_settings['kwargs_fit'], **training_settings['kwargs_val'])

                x_train = x_combined
                y_train = y_combined

                for key in self.model_trained.history.keys():
                    self.model_trained.history[key].extend(unsupervised_model_trained.history[key])

        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(self.model_trained.history['loss'][-1]))
        
        return self.model_trained
    
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