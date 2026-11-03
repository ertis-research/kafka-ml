__author__ = 'Antonio J. Chaves'

from kafka import KafkaConsumer

import os
import logging
import json
import traceback

from config import *
from utils import *
from FederatedKafkaMLAggregationSink import FederatedKafkaMLAggregationSink

from federated_singleIncrementalTraining import SingleIncrementalTraining
from federated_distributedIncrementalTraining import DistributedIncrementalTraining

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

def get_latest_message(consumer, timeout_ms=1000):
  """Returns the newest message received in the control topic, or None if there is no new one.

  Models that arrived while the device was training are stale, only the newest one is used. The last model
  (version -1) is always the newest message, so it is never skipped: using seek_to_end to discard the stale
  models is not safe, as kafka-python resolves its position lazily, in the next read, and it would also
  discard the messages published while training.
  """

  messages = [message for batch in consumer.poll(timeout_ms=timeout_ms).values() for message in batch]
  if len(messages) > 1:
    logging.info("Skipping %d stale models received while training", len(messages) - 1)
  return messages[-1] if messages else None

def classicFederatedTraining(training):
  try:
    consumer_control = KafkaConsumer(training.model_control_topic, bootstrap_servers=training.kml_cloud_bootstrap_server,
                                    enable_auto_commit=False, group_id=training.group_id, auto_offset_reset='earliest')
    
    
    """Starts a Kafka consumer to receive control information"""
    logging.info("Started Kafka consumer in [%s] topic", training.model_control_topic)
    
    sink = FederatedKafkaMLAggregationSink(bootstrap_servers=training.kml_cloud_bootstrap_server, topic=training.aggregation_data_topic,
                                            control_topic=training.aggregation_control_topic, federated_id=training.group_id)

    """Read model from Kafka"""
    while True:
      msg = get_latest_message(consumer_control)
      if msg is None:
        continue
      logging.info("Received message from control topic")

      try:
        consumer_control.commit()

        message = msg.value.decode('utf-8')
        message = json.loads(message)
        logging.info("Received message: %s", str(message))
        
        model = training.load_model(message)
        logging.info("Model received and loaded, trying to start training")
        model.summary()

        training_settings = message['training_settings']

        if 'unsupervised' not in locals() and 'unsupervised' not in globals():
          if training_settings['unsupervised']:
            if training.unsupervised_data_topic is not None:
              unsupervised = True
              logging.info("Received unsupervised topic %s for unlabeled data", str(training.unsupervised_data_topic))
            else:
              unsupervised = False
              logging.info("User deployed semi-supervised training but no unsupervised topic was received for unlabeled data. Performing standard supervised training with labeled data.")
          else:
            unsupervised = False
            logging.info("User deployed supervised training with labeled data.")

        if training.kafka_dataset is None:
          if unsupervised and isinstance(training, (SingleIncrementalTraining, DistributedIncrementalTraining)):
            training.get_kafka_dataset(training_settings)
          else:
            training.get_data(training_settings)
        """Gets the dataset from kafka"""

        if unsupervised:
          if isinstance(training, (SingleIncrementalTraining, DistributedIncrementalTraining)) or training.unsupervised_kafka_dataset is None:
            training.get_unsupervised_data(training_settings)
        """Gets the unlabeled dataset from kafka"""

        logging.info("Starting training with settings: {}".format(training_settings))
        if not unsupervised:
          model_trained = training.train(model, training_settings)
        else:
          model_trained = training.unsupervised_train(model, training_settings)

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

        logging.info("Waiting for the newest model")

      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))

    training.close_online_kafka_consumer()
    training.close_online_unsupervised_kafka_consumer()
    consumer_control.close()
    sink.close()
    logging.info("Model trained and sent the final weights to the aggregation topic")

  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))