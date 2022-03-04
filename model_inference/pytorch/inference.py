__author__ = 'Antonio J Chaves'

import numpy as np

import torch
from torch import nn
from torch.optim import optimizer
from torch.utils.data import DataLoader
from torchvision.transforms import ToTensor

from ignite.engine import Engine, Events, create_supervised_trainer, create_supervised_evaluator
from ignite.metrics import *
from ignite.handlers import ModelCheckpoint
from ignite.contrib.handlers import TensorboardLogger, global_step_from_engine
import torchvision.models as models

from kafka import KafkaConsumer, KafkaProducer

import time
import os
import logging
import sys
import json
import time
import traceback
import optparse

from config import *
from utils import *
from decoders import *


WEIGHTS_PATH='weights.pth'
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
      model_code (str): URL for downloading the code of the trained model
      model_weights (str): URL for downloading the weights of the trained model
      input_format (str): Format of the input data (RAW, AVRO)
      input_config (str): Configuration contains the information needed to process the input
      input_topic (str): Kafka topic for the input data
      output_topic (str): Kafka topic for the output data
      group_id (str): Kafka group id for consuming data
  """
  input_bootstrap_servers = os.environ.get('INPUT_BOOTSTRAP_SERVERS')
  output_bootstrap_servers = os.environ.get('OUTPUT_BOOTSTRAP_SERVERS')
  model_code = os.environ.get('MODEL_ARCH_URL')
  model_weights = os.environ.get('MODEL_URL')
  input_format = os.environ.get('INPUT_FORMAT')
  input_config = os.environ.get('INPUT_CONFIG')
  input_topic = os.environ.get('INPUT_TOPIC')
  output_topic = os.environ.get('OUTPUT_TOPIC')
  group_id = os.environ.get('GROUP_ID')

  return (input_bootstrap_servers, output_bootstrap_servers, model_code, model_weights, input_format, input_config, input_topic, output_topic, group_id)

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

    input_bootstrap_servers, output_bootstrap_servers, model_code, model_weights, input_format, input_config, input_topic, output_topic, group_id = load_environment_vars()
    """Loads the environment information"""
    
    input_config = json.loads(input_config)
    """Parse the configuration"""

    logging.info("Received environment information (input_bootstrap_servers, output_bootstrap_servers, model_url, input_format, input_config, input_topic, output_topic, group_id) ([%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s], [%s])", 
                input_bootstrap_servers, output_bootstrap_servers, model_code, model_weights, input_format, str(input_config), input_topic, output_topic, group_id)
    
    model = download_model(model_code, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received to a PyTorch model (not trained)"""
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model.to(device)

    download_weights(model_weights, WEIGHTS_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received and saves in the filesystem"""

    model.load_state_dict(torch.load(WEIGHTS_PATH))
    """Loads the trained model weights to the downloaded model"""

    model.eval()
        
    consumer = KafkaConsumer(input_topic, bootstrap_servers=input_bootstrap_servers, group_id=group_id, enable_auto_commit=False)
    """Starts a Kafka consumer to receive the information to predict"""
    
    logging.info("Started Kafka consumer in [%s] topic", input_topic)

    output_producer = KafkaProducer(bootstrap_servers=output_bootstrap_servers)
    """Starts a Kafka producer to send the predictions to the output"""
    
    logging.info("Started Kafka producer in [%s] topic", output_topic)

    decoder = DecoderFactory.get_decoder(input_format, input_config)
    """Creates the data decoder"""

    for msg in consumer:
      try:
        start_inference = time.time()

        logging.info("Message received for prediction")

        input_decoded = decoder.decode(msg.value)
        """Decodes the message received"""

        tensored_input = ToTensor()(input_decoded)
        
        tensored_input = torch.unsqueeze(tensored_input, 0)

        tensored_input = tensored_input.to(device)

        prediction_output = model(tensored_input)
        """Predicts the data received"""
        
        print(prediction_output)

        prediction_value = prediction_output.tolist()[0]
        """Gets the prediction value"""

        logging.info("Prediction done: %s", str(prediction_value))

        response = {
          'values': prediction_value
        }
        """Creates the object response"""

        response_to_kafka = json.dumps(response).encode()
        """Encodes the object response"""

  
        output_producer.send(output_topic, response_to_kafka)
        output_producer.flush()
        """Flush the message to be sent now"""
        """Sends the message to Kafka"""

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

