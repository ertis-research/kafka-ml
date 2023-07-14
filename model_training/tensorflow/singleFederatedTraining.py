from mainTraining import *
from callbacks import *


import logging
import re
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

class SingleFederatedTraining(MainTraining):
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
        
        self.model_logger_topic, self.federated_string_id, self.agg_rounds, self.data_restriction, self.min_data, self.agg_strategy = load_federated_environment_vars()

        logging.info("Received federated environment information (model_logger_topic, federated_string_id, agg_rounds, data_restriction, min_data, agg_strategy) ([%s], [%s], [%d], [%s], [%d], [%s])",
                self.model_logger_topic, self.federated_string_id, self.agg_rounds, self.data_restriction, self.min_data, self.agg_strategy)
            

    def get_models(self):
        """Downloads the model and loads it"""
        super().get_single_model()

    def generate_and_send_data_standardization(self):
        """Generates and sends the data standardization"""
        input_shape = str(self.model.input_shape)
        output_shape = str(self.model.output_shape)

        input_shape_sub = (re.search(', (.+?)\)', input_shape))
        output_shape_sub = (re.search(', (.+?)\)', output_shape))


        if input_shape_sub:
            input_shape = input_shape_sub.group(1)
            input_shape = input_shape.replace(',','')
        if output_shape_sub:
            output_shape = output_shape_sub.group(1)
            output_shape = output_shape.replace(',','')

        model_data_standard = {
                'model_format':{'input_shape': input_shape,
                                'output_shape': output_shape,
                            },
                'federated_params': {
                            'federated_string_id': self.federated_string_id,
                            'data_restriction': self.data_restriction,
                            'min_data': self.min_data
                            },
                'framework': 'tf'
                }
        
        logging.info("Model data standard: %s", model_data_standard)


        # Send model info to Kafka to notify that a new model is available
        prod = Producer({'bootstrap.servers': self.bootstrap_servers})

        # Send expected data standardization to Kafka
        prod.produce(self.model_logger_topic, json.dumps(model_data_standard))
        prod.flush()
        logging.info("Send the untrained model to Kafka Model Topic")

    def generate_federated_kafka_topics(self):
        self.model_control_topic = f'FED-{self.federated_string_id}-model_control_topic'
        self.model_data_topic = f'FED-{self.federated_string_id}-model_data_topic'
        self.aggregation_control_topic = f'FED-{self.federated_string_id}-agg_control_topic'

        # Set up the admin client
        admin_client = AdminClient({'bootstrap.servers': self.bootstrap_servers})

        topics_to_create = []

        # Create the new topics
        topics_to_create.append(NewTopic(self.model_control_topic, 1, config={'max.message.bytes': '50000'}))         # 50 KB    
        topics_to_create.append(NewTopic(self.aggregation_control_topic, 1, config={'max.message.bytes': '50000'}))   # 50 KB
        topics_to_create.append(NewTopic(self.model_data_topic, 1, config={'max.message.bytes': '10000000'}))         # 10 MB

        admin_client.create_topics(topics_to_create)

        # Wait for the topic to be created
        topic_created = False
        while not topic_created:
            topic_metadata = admin_client.list_topics(timeout=5)
            if self.model_control_topic in topic_metadata.topics and \
                    self.aggregation_control_topic in topic_metadata.topics and \
                    self.model_data_topic in topic_metadata.topics:
                
                topic_created = True
        
        logging.info("Federated topics created: (model_control_topic, aggregation_control_topic, model_data_topic) = ({}, {}, {})".format(
                                self.model_control_topic, self.aggregation_control_topic, self.model_data_topic))

    
    def parse_metrics(self, model_metrics):
        """Parse the metrics from the model"""
        epoch_training_metrics = {}
        epoch_validation_metrics = {}

        for agg_metrics in model_metrics:
            for keys in agg_metrics['training']:
                if keys not in epoch_training_metrics:
                    epoch_training_metrics[keys] = []
                epoch_training_metrics[keys].append(agg_metrics['training'][keys][-1])

                if keys not in epoch_validation_metrics:
                    epoch_validation_metrics[keys] = []
                epoch_validation_metrics[keys].append(agg_metrics['validation'][keys][-1])

        return epoch_training_metrics, epoch_validation_metrics

    def sendTempMetrics(self, train_metrics, val_metrics):
        """Send the metrics to the backend"""
        results = {
            'train_metrics': train_metrics,
            'val_metrics': val_metrics
        }

        url = self.result_url.replace('results', 'results_metrics')

        retry = 0
        finished = False
        while not finished and retry < RETRIES:
            try:
                data = {'data': json.dumps(results)}
                r = requests.post(url, data=data)
                if r.status_code == 200:
                    finished = True
                    logging.info("Metrics updated!")
                else:
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                    retry += 1
            except Exception as e:
                traceback.print_exc()
                retry += 1
                logging.error("Error sending the metrics to the backend [%s].", str(e))
                time.sleep(SLEEP_BETWEEN_REQUESTS)

    def sendFinalMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
        """Sends the metrics to the control topic"""

        self.stream_timeout = None
        
        return super().sendSingleMetrics(cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix)