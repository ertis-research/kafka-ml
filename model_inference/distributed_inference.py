import numpy as np
import tensorflow as tf
import os
from config import *
import logging
import sys
import json
from kafka import KafkaConsumer, KafkaProducer
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
  bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
  model_url = os.environ.get('MODEL_URL')
  input_format = os.environ.get('INPUT_FORMAT')
  input_config = os.environ.get('INPUT_CONFIG')
  input_topic = os.environ.get('INPUT_TOPIC')
  output_topic = os.environ.get('OUTPUT_TOPIC')
  output_upper = os.environ.get('OUTPUT_UPPER')
  group_id = os.environ.get('GROUP_ID')
  limit = eval(os.environ.get('LIMIT'))

  return (bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, output_upper, group_id, limit)

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

    bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, output_upper, group_id, limit = load_environment_vars()
    """Loads the environment information"""
    
    input_config = json.loads(input_config)
    """Parse the configuration"""

    logging.info("Received environment information (bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, output_upper, group_id, limit) ([%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s])", 
              bootstrap_servers, model_url, input_format, str(input_config), input_topic, output_topic, output_upper, group_id, str(limit))
    
    download_model(model_url, MODEL_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received and saves in the filesystem"""
    
    model = load_model(MODEL_PATH)
    """Loads the model from the filesystem to a Tensorflow model"""
    
    model.summary()
    """Prints the model information"""

    consumer = KafkaConsumer(input_topic, bootstrap_servers=bootstrap_servers, group_id=group_id, enable_auto_commit=False)
    """Starts a Kafka consumer to receive the information to predict"""
    
    logging.info("Started Kafka consumer in [%s] topic", input_topic)

    producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
    """Starts a Kafka producer to send the predictions"""

    decoder = DecoderFactory.get_decoder(input_format, input_config)
    """Creates the data decoder"""

    start_inference = time.time()

    for msg in consumer:
      try:
        logging.info("Message received for prediction")

        input_decoded = decoder.decode(msg.value)
        """Decodes the message received"""

        prediction_to_upper, prediction_output = model.predict(np.array([input_decoded]))
        """Predicts the data received"""
        
        prediction_value = prediction_output.tolist()[0]
        """Gets the prediction value"""

        logging.info("Prediction done: %s", str(prediction_value))

        response = {
          'values': prediction_value
        }
        """Creates the object response"""

        response_to_kafka = json.dumps(response).encode()
        """Encodes the object response"""

        if max(prediction_value) < limit:
          producer.send(output_upper, json.dumps(prediction_to_upper.tolist()).encode())
        else:
          producer.send(output_topic, response_to_kafka)
        """Sends the message to Kafka"""
        
        producer.flush()
        """Flush the message to be sent now"""

        logging.info("Prediction sent to Kafka")
        
        consumer.commit()
        """Commit the consumer offset after processing the message"""

        end_inference = time.time()
        logging.info("Total inference time: %s", str(end_inference - start_inference))

      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))
  except Exception as e:
    traceback.print_exc()
    logging.error("Error in main [%s]. Service will be restarted.", str(e))