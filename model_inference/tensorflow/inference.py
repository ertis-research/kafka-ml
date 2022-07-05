__author__ = 'Cristian Martin Fdz'

import numpy as np
import tensorflow as tf
import os
from config import *
import logging
import sys
import json
from confluent_kafka import Producer, Consumer
import traceback
from utils import *
from decoders import *
import time

MODEL_PATH='model.h5'
'''Path of the trained model'''

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

MAX_MESSAGES_TO_COMMIT = 16
'''Maximum number of messages to commit at a time'''

def load_environment_vars():
  """Loads the environment information received from dockers
  bootstrap_servers, trained_model_url, input_topic, output_topic
  Returns:
      bootstrap_servers (str): list of bootstrap server for the Kafka connection
      model_url (str): URL for downloading the trained model
      input_format (str): Format of the input data (RAW, AVRO)
      input_config (str): Configuration contains the information needed to process the input
      input_topic (str): Kafka topic for the input data
      output_topic (str): Kafka topic for the output data
      group_id (str): Kafka group id for consuming data
  """
  input_bootstrap_servers = os.environ.get('INPUT_BOOTSTRAP_SERVERS')
  output_bootstrap_servers = os.environ.get('OUTPUT_BOOTSTRAP_SERVERS')
  model_url = os.environ.get('MODEL_URL')
  input_format = os.environ.get('INPUT_FORMAT')
  input_config = os.environ.get('INPUT_CONFIG')
  input_topic = os.environ.get('INPUT_TOPIC')
  output_topic = os.environ.get('OUTPUT_TOPIC')
  group_id = os.environ.get('GROUP_ID')

  return (input_bootstrap_servers, output_bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, group_id)

if __name__ == '__main__':
  try:
    if DEBUG:
      logging.basicConfig(
          stream=sys.stdout,
          level=logging.DEBUG,
          format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
          datefmt='%Y-%m-%d %H:%M:%S',
          )
    else:
      logging.basicConfig(
          stream=sys.stdout,
          level=logging.INFO,
          format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s',
          datefmt='%Y-%m-%d %H:%M:%S',
          )
    """Configures the logging"""

    gpus = tf.config.experimental.list_physical_devices('GPU')
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)

    input_bootstrap_servers, output_bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, group_id = load_environment_vars()
    """Loads the environment information"""
    
    upper_bootstrap_servers = os.environ.get('UPPER_BOOTSTRAP_SERVERS')
    output_upper = os.environ.get('OUTPUT_UPPER')
    if upper_bootstrap_servers is not None and output_upper is not None:
      limit = eval(os.environ.get('LIMIT'))
    """Loads the distributed environment information"""

    if upper_bootstrap_servers is not None and output_upper is not None and limit is not None:
      distributed = True
    else:
      distributed = False
    """Flag to work with distributed models"""

    input_config = json.loads(input_config)
    """Parse the configuration"""

    if distributed:
      logging.info("Received environment information (input_bootstrap_servers, output_bootstrap_servers, upper_bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, output_upper, group_id, limit) ([%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s])", 
              input_bootstrap_servers, output_bootstrap_servers, upper_bootstrap_servers, model_url, input_format, str(input_config), input_topic, output_topic, output_upper, group_id, str(limit))
    else:
      logging.info("Received environment information (input_bootstrap_servers, output_bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, group_id) ([%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s])", 
              input_bootstrap_servers, output_bootstrap_servers, model_url, input_format, str(input_config), input_topic, output_topic, group_id)
    
    download_model(model_url, MODEL_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received and saves in the filesystem"""
    
    model = load_model(MODEL_PATH)
    """Loads the model from the filesystem to a Tensorflow model"""
    
    model.summary()
    """Prints the model information"""

    consumer = Consumer({'bootstrap.servers': input_bootstrap_servers,'group.id': 'group_id','auto.offset.reset': 'earliest','enable.auto.commit': False})
    consumer.subscribe([input_topic])
    """Starts a Kafka consumer to receive the information to predict"""
    
    logging.info("Started Kafka consumer in [%s] topic", input_topic)

    output_producer = Producer({'bootstrap.servers': output_bootstrap_servers})
    """Starts a Kafka producer to send the predictions to the output"""
    
    logging.info("Started Kafka producer in [%s] topic", output_topic)

    if distributed:
      upper_producer = Producer({'bootstrap.servers': upper_bootstrap_servers})
      """Starts a Kafka producer to send the predictions to upper model"""
    
      logging.info("Started Kafka producer in [%s] topic", output_upper)

    decoder = DecoderFactory.get_decoder(input_format, input_config)
    """Creates the data decoder"""

    commitedMessages = 0
    """Number of messages commited"""

    while True:
      msg = consumer.poll(1.0)

      if msg is None:
          continue
      if msg.error():
          print("Consumer error: {}".format(msg.error()))
          continue

      try:
        start_inference = time.time()

        logging.debug("Message received for prediction")

        input_decoded = decoder.decode(msg.value())
        """Decodes the message received"""

        if distributed:
          prediction_to_upper, prediction_output = model.predict(input_decoded)
        else:
          prediction_output = model.predict(input_decoded)
        """Predicts the data received"""
        
        prediction_value = prediction_output.tolist()[0]
        """Gets the prediction value"""

        logging.debug("Prediction done: %s", str(prediction_value))

        response = {
          'values': prediction_value
        }
        """Creates the object response"""

        response_to_kafka = json.dumps(response).encode()
        """Encodes the object response"""

        commitedMessages += 1

        if distributed and max(prediction_value) < limit:
          upper_producer.produce(output_upper, prediction_to_upper.tobytes())
          ## Cada ciertos mensajes, 10 ej. commit.
          if commitedMessages >= MAX_MESSAGES_TO_COMMIT:  
            upper_producer.flush()
          """Flush the message to be sent now"""
        else:
          output_producer.produce(output_topic, response_to_kafka)
          ## Cada ciertos mensajes, 10 ej. commit.
          if commitedMessages >= MAX_MESSAGES_TO_COMMIT:  
            output_producer.flush()
          """Flush the message to be sent now"""
        """Sends the message to Kafka"""

        logging.debug("Prediction sent to Kafka")
        

        if commitedMessages >= MAX_MESSAGES_TO_COMMIT:          
          consumer.commit()
          commitedMessages = 0
          """Commit the consumer offset after processing the message"""
          logging.debug("Commited messages to Kafka")

        end_inference = time.time()
        logging.debug("Total inference time: %s", str(end_inference - start_inference))
      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))
  except Exception as e:
    traceback.print_exc()
    logging.error("Error in main [%s]. Service will be restarted.", str(e))

