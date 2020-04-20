__author__ = 'Cristian Martin Fdz'

import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow_io.kafka as kafka_io
import os
import urllib
from config import *
import logging
import sys
import json
from kafka import KafkaConsumer
import requests
import time
import traceback

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
      result_url (str): URL for downloading the pre model
      deployment_id (int): deployment ID of the application
      batch (int): Batch size used for training
      kwargs_fit (:obj:json): JSON with the arguments used for training
  """
  bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
  result_url = os.environ.get('RESULT_URL')
  control_topic = os.environ.get('CONTROL_TOPIC')
  deployment_id = int(os.environ.get('DEPLOYMENT_ID'))
  batch = int(os.environ.get('BATCH'))
  kwargs_fit = json.loads(os.environ.get('KWARGS_FIT').replace("'", '"'))

  return (bootstrap_servers, result_url, control_topic, deployment_id, batch, kwargs_fit)

def download_pre_model(result_url):
  """Downloads the pre-model from the URL received and saves it in the filesystem
  Args:
      result_url(str): URL of the pre-model 
  """
  finished = False
  retry = 0
  while not finished and retry < RETRIES:
    try:
      filedata = urllib.request.urlopen(result_url)
      datatowrite = filedata.read()
      with open(PRE_MODEL_PATH, 'wb') as f:
          f.write(datatowrite)
      finished = True
      logging.info("Downloaded file model from server!")
    except Exception as e:
      retry +=1
      logging.error("Error downloading the model file [%s]", str(e))
      time.sleep(SLEEP_BETWEEN_REQUESTS)


def string_to_tensorflow_type(out_type):
  """Converts a string with the same name to a Tensorflow type.
  Acceptable types are half, float, double, int32, uint16, uint8, 
            int16, int8, int64, string, bool.
  Args:
      out_type (str): Output type to convert
  Returns:
    Tensorflow DType: Tensorflow DType of the intput
  """

  if out_type == 'half':
    return tf.half
  elif out_type == 'float':
    return tf.float
  elif out_type == 'double':
    return tf.double
  elif out_type == 'int64':
    return tf.int64
  elif out_type == 'int32':
    return tf.int32
  elif out_type == 'int16':
    return tf.int16 
  elif out_type == 'int8':
    return tf.int8
  elif out_type == 'uint16':
    return tf.uint16 
  elif out_type == 'uint8':
    return tf.uint8 
  elif out_type == 'string':
    return tf.string
  elif out_type == 'bool':
    return tf.bool
  else:
    raise Exception('string_to_tensorflow_type: Unsupported type')

def load_model():
  """Returns the model saved previously in the filesystem.
  
  Returns:
    Tensorflow model: tensorflow model loaded
  """

  model = keras.models.load_model(PRE_MODEL_PATH)
  if DEBUG:
    model.summary()
    """Prints model architecture"""
  return model

def decode_raw(x, output_type, output_reshape):
  """Decodes the raw data received from Kafka and reshapes it if needed.

    Args:
      x (raw): input data
      output_type (tensorflow type): output type of the received data
      reshape (array): reshape the tensorflow type (optional)
    
    Returns:
      DType: raw data to tensorflow model loaded
  """
  res = tf.io.decode_raw(x, out_type=output_type)
  res = tf.reshape(res, output_reshape)
  return res

def decode_input(x, y, output_type_x, reshape_x, output_type_y, reshape_y):
  """Decodes the input data received from Kafka and reshapes it if needed.

    Args:
      x (bytes): train data
      output_type_x (:obj:DType): output type of the train data
      reshape_x (:obj:`list`): reshape the tensorflow train data (optional)
      y (bytes): label data
      out_type_y (:obj:DType): output type of the label data
      reshape_y (:obj:`list`): reshape the tensorflow label data (optional)
    
    Returns:
      tuple: tuple with the (train, label) data received
  """

  x = decode_raw(x, output_type_x, reshape_x)
  x = tf.image.convert_image_dtype(x, tf.float32)
  y = decode_raw(y, output_type_y, reshape_y)
  return (x, y)

def raw_kafka(boostrap_servers, kafka_topic, out_type_x, out_type_y, reshape_x, reshape_y, batch):
  """Obtains the data and labels for training from Kafka

    Args:
      boostrap_servers (str): list of boostrap servers for the connection with Kafka
      kafka_topic (str): Kafka topic   out_type_x, out_type_y, reshape_x, reshape_y) (raw): input data
      out_type_x (:obj:DType): output type of the train data
      reshape_x (:obj:array): reshape for training data (optional)
      out_type_y (:obj:DType): output type of the label data
      reshape_y (obj:array): reshape for label data (optional)
      batch (int): batch size for training
    
    Returns:
      train_kafka: training data and labels from Kafka
  """
  logging.info("Starts receiving training data from Kafka servers [%s] with topics [%s]", boostrap_servers,  kafka_topic)
  train_data = kafka_io.KafkaDataset([kafka_topic], servers=boostrap_servers, group=kafka_topic, eof=True, message_key=True).map(lambda x, y: decode_input(x, y, out_type_x, reshape_x, out_type_y, reshape_y)).batch(batch)                                  
  
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

    bootstrap_servers, result_url, control_topic, deployment_id, batch, kwargs_fit  = load_environment_vars()
    """Loads the environment information"""

    logging.info("Received environment information (bootstrap_servers, result_url, control_topic, deployment_id, batch, kwargs_fit ) ([%s], [%s], [%s], [%d], [%d], [%s])", 
              bootstrap_servers, result_url, control_topic, deployment_id, batch, str(kwargs_fit))
    
    download_pre_model(result_url)
    """Downloads the model from the URL received and saves in the filesystem"""
    
    model = load_model()
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
                    'configuration' : ..,
                    'description': ..,
                    'validation_rate' : ..,
                    'total_msg': ..
                }
            """
            kafka_topic = data['topic']
            logging.info("Received control confirmation of data from Kafka for deployment ID %s. Ready to receive data from topic %s with batch %d", str(kafka_topic), deployment_id, batch)
            train_kafka = None
            if data['input_format']=='RAW':
              logging.info("RAW input format received.")
              configuration = data['configuration']
              out_type_x = string_to_tensorflow_type(configuration['data_type'])
              out_type_y = string_to_tensorflow_type(configuration['label_type'])
              x_reshape = configuration['data_reshape']
              y_reshape = configuration['label_reshape']
              
              if x_reshape is not None:
                x_reshape = np.fromstring(x_reshape, dtype=int, sep=' ')
              if y_reshape is not None:
                y_reshape = np.fromstring(y_reshape, dtype=int, sep=' ')
              kafka_dataset = raw_kafka(bootstrap_servers, kafka_topic , out_type_x, out_type_y, x_reshape, y_reshape, batch)
              ok_training = True

            elif data['input_format'] == 'AVRO':
              logging.info("AVRO input format received")
              pass
            
            if ok_training:
              logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
              
              split = int((1-data['validation_rate'])*(data['total_msg']/batch))
              validation_size= (data['total_msg']/batch)-split
              logging.info("Training batch size %d and validation batch size %d", split, validation_size)
              
              train_dataset = kafka_dataset.take(split)
              """Splits dataset for training"""

              validation_dataset = kafka_dataset.skip(split)
              """Splits dataset for validation"""

              model_trained = model.fit(train_dataset, **kwargs_fit)
              """Trains the model"""

              logging.info("Model trainned! loss (%s), accuracy(%s)", model_trained.history['loss'], model_trained.history['accuracy'])

              if validation_size > 0:
                model_validate = model.evaluate(validation_dataset)
                """Validates the model"""
                logging.info("Validation results: "+str(model_validate))

              retry = 0
              finished = False
              
              while not finished and retry < RETRIES:
                try:
                  model.save(TRAINED_MODEL_PATH)
                  """Saves the trained model in the filesystem"""
                  
                  files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb')}

                  results = {
                          'train_loss_hist': str(model_trained.history['loss']),
                          'train_acc_hist':  str(model_trained.history['accuracy']),
                  }
                  if validation_size > 0:
                    """if validation has been defined"""
                    results['val_loss'] = float(model_validate[0]) # Loss is in the first element
                    results['val_acc'] = float(model_validate[1]) # Accuracy in the second

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
              consumer.close(autocommit=False)
      
      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))
  except Exception as e:
      logging.error("Error in main [%s]. Service will be restarted.", str(e))

