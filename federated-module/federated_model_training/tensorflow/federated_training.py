__author__ = 'Antonio J. Chaves'

from kafka import KafkaConsumer

import os
import logging
import json
import traceback

from config import *
from utils import *
from FederatedKafkaMLAggregationSink import FederatedKafkaMLAggregationSink
from federated_singleClassicTraining import SingleClassicTraining
from federated_singleIncrementalTraining import SingleIncrementalTraining
from federated_distributedClassicTraining import DistributedClassicTraining
from federated_distributedIncrementalTraining import DistributedIncrementalTraining

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

def main():
  try:
    configure_logging()
    """Configures the logging"""

    select_gpu()
    """Configures the GPU"""

    case = int(os.environ.get('CASE')) if os.environ.get('CASE') else 1

    if case == FEDERATED_NOT_DISTRIBUTED_NOT_INCREMENTAL:
      training = SingleClassicTraining()
    elif case == FEDERATED_NOT_DISTRIBUTED_INCREMENTAL:
      training = SingleIncrementalTraining()
    elif case == FEDERATED_DISTRIBUTED_NOT_INCREMENTAL:
      training = DistributedClassicTraining()
    elif case == FEDERATED_DISTRIBUTED_INCREMENTAL:
      training = DistributedIncrementalTraining()
    else:
      raise ValueError(case) 
    """Gets type of training"""
      
    consumer_control = KafkaConsumer(training.model_control_topic, bootstrap_servers=training.kml_cloud_bootstrap_server,
                                    enable_auto_commit=False, group_id=training.group_id, auto_offset_reset='earliest')
    
    
    """Starts a Kafka consumer to receive control information"""
    logging.info("Started Kafka consumer in [%s] topic", training.model_control_topic)
    
    sink = FederatedKafkaMLAggregationSink(bootstrap_servers=training.kml_cloud_bootstrap_server, topic=training.aggregation_data_topic,
                                     control_topic=training.aggregation_control_topic, federated_id=training.group_id)

    """Read model from Kafka"""
    for msg in consumer_control:
      logging.info("Received message from control topic")

      try:
        consumer_control.commit()
        consumer_control.poll()
        consumer_control.seek_to_end()

        message = msg.value.decode('utf-8')
        message = json.loads(message)
        logging.info("Received message: %s", str(message))
        
        model = training.load_model(message)
        logging.info("Model received and loaded, trying to start training")
        model.summary()

        training_settings = message['training_settings']

        if training.kafka_dataset is None:
          training.get_data(training_settings)

        logging.info("Starting training with settings: {}".format(training_settings))
        model_trained = training.train(model, training_settings)

        epoch_training_metrics, epoch_validation_metrics = training.save_metrics(model_trained)
        metrics = {
            'training': epoch_training_metrics,
            'validation': epoch_validation_metrics
        }

        sink.send_model_and_metrics(model, metrics, message['version'], training.total_msg)
        logging.info("Model sent to aggregation topic, boostrap server [%s], [%s]", training.aggregation_data_topic, training.kml_cloud_bootstrap_server) 

        if message['version'] == -1:
          logging.info("Last model received, stopping training")
          break

        logging.info("Seeked to end of topic, waiting for the newest model")

      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))

    consumer_control.close()
    sink.close()
    logging.info("Model trained and sent the final weights to the aggregation topic")

  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))

if __name__ == "__main__":
  main()