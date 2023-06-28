from kafka import KafkaConsumer

import time
import os
import logging
import json
import time
import traceback

from decoders import *

from singleClassicTraining import SingleClassicTraining
from distributedClassicTraining import DistributedClassicTraining
from singleIncrementalTraining import SingleIncrementalTraining
from distributedIncrementalTraining import DistributedIncrementalTraining


def CloudBasedTraining(training):
    training.get_models()
    """Downloads the models from the URLs received, saves and loads them from the filesystem to Tensorflow models"""
    
    consumer = KafkaConsumer(training.control_topic, bootstrap_servers=training.bootstrap_servers, auto_offset_reset='earliest', enable_auto_commit=False)
    """Starts a Kafka consumer to receive the datasource information from the control topic"""
    
    logging.info("Created and connected Kafka consumer for control topic")
    datasource_received = False
    while datasource_received is False:
      """Loop until a datasource is received"""

      msg = next(consumer)
      """Gets a new message from Kafka control topic"""
      logging.info("Message received in control topic")
      logging.info(msg)

      try:
        ok_training = False
        data = None
        if msg.key is not None:
          received_deployment_id = int.from_bytes(msg.key, byteorder='big')
          if received_deployment_id == training.deployment_id:
            """Whether the deployment ID received matches the received in this task, then it is a datasource for this task."""
            
            data = json.loads(msg.value)
            """Data received from Kafka control topic. Data is a JSON with this format:
                dic={
                    'topic': ..,
                    'input_format': ..,
                    'input_config' : ..,
                    'description': ..,
                    'validation_rate' : ..,
                    'total_msg': ..
                }
            """
            kafka_topic = data['topic']
            logging.info("Received control confirmation of data from Kafka for deployment ID %s. Ready to receive data from topic %s with batch %d", training.deployment_id, str(kafka_topic), training.batch)
            
            decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
            """Gets the decoder from the information received"""

            kafka_dataset = training.get_data(kafka_topic, decoder)
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(training.kwargs_fit))
                        
            splits = None
            
            if isinstance(training, SingleClassicTraining) or isinstance(training, DistributedClassicTraining):
              splits = training.get_splits(data, kafka_dataset)
            """Splits the dataset for training"""

            logging.info("Splitting done, training is going to start.")
            
            start = time.time()

            if isinstance(training, DistributedClassicTraining) or isinstance(training, DistributedIncrementalTraining):
              training.configure_distributed_models()
            """Distributed models configuration"""

            training_results = training.train(splits, kafka_dataset, decoder, start)
            """Trains the model"""

            end = time.time()
            logging.info("Total training time: %s", str(end - start))
            logging.info("Model trained! Loss: %s", str(training_results['model_trained'].history['loss'][-1]))

            epoch_training_metrics, epoch_validation_metrics, test_metrics = training.saveMetrics(training_results['model_trained'], training_results['incremental_validation'])
            """Saves training metrics"""

            if isinstance(training, SingleClassicTraining) or isinstance(training, DistributedClassicTraining):
              test_metrics = training.test(splits, epoch_training_metrics, test_metrics)
            """Tests the model"""
            
            cf_generated = None
            cf_matrix = None

            if isinstance(training, SingleClassicTraining) or isinstance(training, SingleIncrementalTraining):
              cf_generated, cf_matrix = training.getConfussionMatrix(splits, training_results)
            """Creates confussion matrix"""

            logging.info(f"Training metrics per epoch {epoch_training_metrics}")
            logging.info(f"Validation metrics per epoch {epoch_validation_metrics}")
            logging.info(f"Test metrics {test_metrics}")
            
            dtime = end - start
            
            datasource_received = training.sendMetrics(cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix)
            """Sends metrics to result URL"""

      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))

  
    logging.info("Cloud-based training (%s) finished", type(training).__name__)
