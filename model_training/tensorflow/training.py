__author__ = 'Cristian Martin Fdz'

import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow_io.kafka as kafka_io

from kafka import KafkaConsumer

from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

import time
import os
import logging
import sys
import json
import requests
import time
import traceback
import subprocess as sp

from config import *
from utils import *
from decoders import *

PRE_MODEL_PATH='pre_model.h5'
'''Path of the received pre-model'''

TRAINED_MODEL_PATH='trained_model.h5'
'''Path of the trained model'''

CONFUSSION_MODEL_IMAGE = 'confusion_matrix.png'
'''Path of the confussion matrix image'''

RETRIES = 10
'''Number of retries for requests'''

SLEEP_BETWEEN_REQUESTS = 5
'''Number of seconds between failed requests'''

def select_gpu():
  ACCEPTABLE_AVAILABLE_MEMORY = 1024
  COMMAND = "nvidia-smi --query-gpu=memory.free --format=csv"

  try:
    _output_to_list = lambda x: x.decode('ascii').split('\n')[:-1]
    memory_free_info = _output_to_list(sp.check_output(COMMAND.split()))[1:]
    memory_free_values = [int(x.split()[0]) for i, x in enumerate(memory_free_info)]
    
    available_gpus = [i for i, x in enumerate(memory_free_values) if x > ACCEPTABLE_AVAILABLE_MEMORY]
    print("Available GPUs:", available_gpus)
    if len(available_gpus) > 1:
        available_gpus = [memory_free_values.index(max(memory_free_values))]
        print("Using GPU:", available_gpus)
        
    os.environ["CUDA_VISIBLE_DEVICES"] = ','.join(map(str, available_gpus))
  except Exception as e:
    print('"nvidia-smi" is probably not installed. GPUs are not masked.', e)

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
  confussion_matrix = json.loads(os.environ.get('CONF_MAT_CONFIG').replace("'", '"'))

  return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix)

def get_train_data(boostrap_servers, kafka_topic, group, decoder):
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
  train_data = kafka_io.KafkaDataset(kafka_topic.split(','), servers=boostrap_servers, group=group, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))                                 
  
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

    bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix  = load_environment_vars()
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
            logging.info("Received control confirmation of data from Kafka for deployment ID %s. Ready to receive data from topic %s with batch %d", deployment_id, str(kafka_topic), batch)
            
            decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
            """Gets the decoder from the information received"""

            kafka_dataset = get_train_data(bootstrap_servers, kafka_topic, result_id, decoder)
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
                        
            training_size = int((1-(data['validation_rate']+data['test_rate']))*(data['total_msg']))
            validation_size= int( data['validation_rate'] * data['total_msg'])
            test_size= int( data['test_rate'] * data['total_msg'])

            logging.info("Training batch size %d, validation batch size %d and test batch size %d", training_size, validation_size, test_size)
            
            start = time.time()

            train_dataset = kafka_dataset.take(training_size).batch(batch)
            """Splits dataset for training"""

            test_dataset = kafka_dataset.skip(training_size)

            if validation_size > 0 and test_size > 0:
              """If validation and test size are greater than 0, then split the dataset for validation and test"""
              validation_dataset = test_dataset.skip(test_size).batch(batch)
              test_dataset = test_dataset.take(test_size).batch(batch)
            elif validation_size > 0:
              """If only validation size is greater than 0, then split the dataset for validation"""
              validation_dataset = test_dataset.batch(batch)
              test_dataset = None
            elif test_size > 0:
              """If only test size is greater than 0, then split the dataset for test"""
              validation_dataset = None
              test_dataset = test_dataset.batch(batch)
            else:
              """If no validation or test size is greater than 0, then split the dataset for training"""
              validation_dataset = None
              test_dataset = None
            
            logging.info("Splitting done, training is going to start.")

            model_trained = model.fit(train_dataset, validation_data=validation_dataset, **kwargs_fit)
            """Trains the model"""

            end = time.time()
            logging.info("Total training time: %s", str(end - start))
            logging.info("Model trained! Loss: %s",str(model_trained.history['loss'][-1]))

            epoch_training_metrics   = {}
            epoch_validation_metrics = {}
            test_metrics = {}

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

            if test_size > 0:
              logging.info("Model ready to test with configuration %s", str(kwargs_val))
              evaluation = model.evaluate(test_dataset, **kwargs_val)
              """Validates the model"""
              logging.info("Model tested!")
            
              for k, i in zip(epoch_training_metrics.keys(), range(len(epoch_training_metrics.keys()))):
                test_metrics[k] = [evaluation[i]]


            cf_generated = False
            cf_matrix = None
            if confussion_matrix and test_size > 0:
              try:
                logging.info("Trying to generate confussion matrix")

                evaluation = model.predict(test_dataset, **kwargs_val)
                '''Predicts test data on the trained model'''

                evaluation = np.argmax(evaluation, axis=1)                
                '''arg max for each sub list'''
                  
                y_true = np.concatenate([y for _, y in test_dataset], axis=0)

                cf_matrix = confusion_matrix(y_true, evaluation)
                '''Generates the confussion matrix'''

                logging.info("Confussion matrix generated")

                sns.set(rc = {'figure.figsize':(10,8)})
                
                lab = np.around(cf_matrix.astype('float') / cf_matrix.sum(axis=1)[:, np.newaxis], decimals=4)
                ax = sns.heatmap(lab, annot=True, fmt='.2%', cmap="Blues")

                ax.set_title('Confusion Matrix\n')
                ax.set_xlabel('\nPredicted Values\n')
                ax.set_ylabel('Real values') 

                plt.savefig(CONFUSSION_MODEL_IMAGE, dpi=200, transparent=True)

                cf_generated = True
                logging.info("Generated confussion matrix successfully")
              except:
                 logging.info("Could not generate confussion matrix")
           
            retry, finished = 0, False
            while not finished and retry < RETRIES:
              try:
                model.save(TRAINED_MODEL_PATH)
                """Saves the trained model in the filesystem"""
                
                files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb'),
                        'confussion_matrix': open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}              

                results = {
                        'train_metrics':  epoch_training_metrics,
                        'val_metrics':  epoch_validation_metrics,
                        'test_metrics':  test_metrics,
                        'training_time': round(end - start, 4),
                        'confusion_matrix': cf_matrix.tolist() if cf_generated else None
                }

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

