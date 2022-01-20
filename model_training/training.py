__author__ = 'Cristian Martin Fdz'

import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow_io.kafka as kafka_io

from kafka import KafkaConsumer

import time
import os
import logging
import sys
import json
import requests
import time
import traceback

from config import *
from utils import *
from decoders import *

PRE_MODEL_PATH='pre_model.h5'
'''Path of the received pre-model'''

TRAINED_MODEL_PATH='trained_model.h5'
'''Path of the trained model'''

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

def load_environment_vars():
  """Loads the environment information receivedfrom dockers
  boostrap_servers, result_url, result_update_url, control_topic, deployment_id, batch, kwargs_fit 
  Returns:
      boostrap_servers (str): list of boostrap server for the Kafka connection
      result_url (str): URL for downloading the untrained model
      result_id (str): Result ID of the model
      control_topic(str): Control topic
      deployment_id (int): deployment ID of the application
      batch (int): Batch size used for training
      kwargs_fit (:obj:json): JSON with the arguments used for training
      kwargs_val (:obj:json): JSON with the arguments used for validation
  """
  bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
  result_url = os.environ.get('RESULT_URL')
  result_id = os.environ.get('RESULT_ID')
  control_topic = os.environ.get('CONTROL_TOPIC')
  deployment_id = int(os.environ.get('DEPLOYMENT_ID'))
  batch = int(os.environ.get('BATCH'))
  kwargs_fit = json.loads(os.environ.get('KWARGS_FIT').replace("'", '"'))
  kwargs_val = json.loads(os.environ.get('KWARGS_VAL').replace("'", '"'))

  return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val)

def get_train_data(boostrap_servers, kafka_topic, group, batch, decoder):
  """Obtains the data and labels for training from Kafka

    Args:
      boostrap_servers (str): list of boostrap servers for the connection with Kafka
      kafka_topic (str): Kafka topic   out_type_x, out_type_y, reshape_x, reshape_y) (raw): input data
      batch (int): batch size for training
      decoder(class): decoder to decode the data
    
    Returns:
      train_kafka: training data and labels from Kafka
  """
  logging.info("Starts receiving training data from Kafka servers [%s] with topics [%s]", boostrap_servers,  kafka_topic)
  train_data = kafka_io.KafkaDataset([kafka_topic], servers=boostrap_servers, group=group, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y)).batch(batch)                                  
  
  return train_data

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

    bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val  = load_environment_vars()
    """Loads the environment information"""

    logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s])", 
              bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, str(kwargs_fit), str(kwargs_val))
    
    download_model(result_url, PRE_MODEL_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received and saves in the filesystem"""
    
    model = load_model(PRE_MODEL_PATH)
    """Loads the model from the filesystem to a Tensorflow model"""
    
    consumer = KafkaConsumer(control_topic, bootstrap_servers=bootstrap_servers, auto_offset_reset='earliest', enable_auto_commit=False)
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
          if received_deployment_id == deployment_id:
            """Whether the deployment ID received matches the received in this task, then it is a datasource for this task."""
            
            data = json.loads(msg.value)
            """ Data received from Kafka control topic. Data is a JSON with this format:
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
            logging.info("Received control confirmation of data from Kafka for deployment ID %s. Ready to receive data from topic %s with batch %d", str(kafka_topic), deployment_id, batch)
            
            decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
            """Gets the decoder from the information received"""

            kafka_dataset = get_train_data(bootstrap_servers, kafka_topic, result_id, batch, decoder)
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
            
            split = int((1-data['validation_rate'])*(data['total_msg']/batch))
            validation_size= (data['total_msg']/batch)-split
            logging.info("Training batch size %d and validation batch size %d", split, validation_size)
            
            start = time.time()

            train_dataset = kafka_dataset.take(split).cache().repeat()
            """Splits dataset for training"""

            validation_dataset = kafka_dataset.skip(split).cache().repeat()
            """Splits dataset for validation"""
            
            logging.info("Splitting done, training is going to start.")

            model_trained = model.fit(train_dataset, steps_per_epoch=split, **kwargs_fit)
            """Trains the model"""

            end = time.time()
            logging.info("Total training time: %s", str(end - start))

            train_loss =  model_trained.history['loss'][-1]
            """Get last value of lost"""

            logging.info("Model trainned! Loss: %s",str(train_loss))

            if validation_size > 0:
              logging.info("Model ready to evaluation with configuration %s", str(kwargs_val))
              evaluation = model.evaluate(validation_dataset, **kwargs_val)
              """Validates the model"""
              logging.info("Model evaluated!")

            retry = 0
            finished = False

            metrics_dic = {}
            train_metrics = ""
            for key in model_trained.history.keys():
              if key!='loss':
                metrics_dic[key] = model_trained.history[key][-1]
                train_metrics += key+": "+str(round(model_trained.history[key][-1],10))+"\n"
            """Get all metrics except the loss"""

            while not finished and retry < RETRIES:
              try:
                model.save(TRAINED_MODEL_PATH)
                """Saves the trained model in the filesystem"""
                
                files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb')}

                results = {
                        'train_loss': round(train_loss,10),
                        'train_metrics':  train_metrics,
                }
                if validation_size > 0:
                  """if validation has been defined"""
                  results['val_loss'] = float(evaluation[0]) # Loss is in the first element
                  results['val_metrics'] =''
                  index = 1
                  for key in metrics_dic:
                    results['val_metrics']+=key+": "+str(round(evaluation[index], 10))+"\n"
                    index += 1

                data = {'data' : json.dumps(results)}
                logging.info("Sending result data to backend")
                r = requests.post(result_url, files=files, data=data)
                """Sends the training results to the backend"""

                if r.status_code == 200:
                  finished = True
                  datasource_received = True
                  logging.info("Result data sent correctly to backend!!")
                else:
                  time.sleep(SLEEP_BETWEEN_REQUESTS)
                  retry+=1
              except Exception as e:
                traceback.print_exc()
                retry+=1
                logging.error("Error sending the result to the backend [%s].", str(e))
                time.sleep(SLEEP_BETWEEN_REQUESTS)
              consumer.close(autocommit=True)
      
      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))
  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))

