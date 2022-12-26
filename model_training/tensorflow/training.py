__author__ = 'Cristian Martin Fdz'

import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow_io as tfio
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

class CustomCallback(keras.callbacks.Callback):
  def __init__(self, result_url, case, tensorflow_models=None):
    super().__init__()
    self.case = case
    self.tensorflow_models = tensorflow_models
    if self.case == NOT_DISTRIBUTED_NOT_INCREMENTAL or self.case == NOT_DISTRIBUTED_INCREMENTAL:
      self.url = result_url.replace('results', 'results_metrics')
      self.epoch_training_metrics = {}
      self.epoch_validation_metrics = {}
    elif self.case == DISTRIBUTED_NOT_INCREMENTAL or self.case == DISTRIBUTED_INCREMENTAL:
      self.url = []
      for elem in result_url:
        self.url.append(elem.replace('results', 'results_metrics'))
      self.epoch_training_metrics = []
      self.epoch_validation_metrics = []
      for i in range(len(self.tensorflow_models)):
        self.epoch_training_metrics.append({})
        self.epoch_validation_metrics.append({})

  def __send_data(self, logs, inc_val):
    finished = False

    if not inc_val:
      if self.case == NOT_DISTRIBUTED_NOT_INCREMENTAL or self.case == NOT_DISTRIBUTED_INCREMENTAL:
        for k, v in logs.items():
          if not k.startswith("val_"):
            if not k in self.epoch_training_metrics.keys():
              self.epoch_training_metrics[k] = [v]
            else:
              self.epoch_training_metrics[k].append(v)
          else:
            if not k[4:] in self.epoch_validation_metrics.keys():
              self.epoch_validation_metrics[k[4:]] = [v]
            else:
              self.epoch_validation_metrics[k[4:]].append(v)
      elif self.case == DISTRIBUTED_NOT_INCREMENTAL or self.case == DISTRIBUTED_INCREMENTAL:
        for i, m in zip(range(len(self.tensorflow_models)), self.tensorflow_models):
          for k, v in logs.items():
            if m.name in k:
              if not k.startswith("val_"):
                if not k[len(m.name)+1:] in self.epoch_training_metrics[i].keys():
                  self.epoch_training_metrics[i][k[len(m.name)+1:]] = [v]
                else:
                  self.epoch_training_metrics[i][k[len(m.name)+1:]].append(v)
              else:
                if not k[4+len(m.name)+1:] in self.epoch_validation_metrics[i].keys():
                  self.epoch_validation_metrics[i][k[4+len(m.name)+1:]] = [v]
                else:
                  self.epoch_validation_metrics[i][k[4+len(m.name)+1:]].append(v)
    else:
      if self.case == NOT_DISTRIBUTED_INCREMENTAL:
        for k, v in logs.items():
          if not k in self.epoch_validation_metrics.keys():
            self.epoch_validation_metrics[k] = [v]
          else:
            self.epoch_validation_metrics[k].append(v)
      elif self.case == DISTRIBUTED_INCREMENTAL:
        for i, m in zip(range(len(self.tensorflow_models)), self.tensorflow_models):
          for k, v in logs.items():
            if m.name in k:
              if not k[len(m.name)+1:] in self.epoch_validation_metrics[i].keys():
                self.epoch_validation_metrics[i][k[len(m.name)+1:]] = [v]
              else:
                self.epoch_validation_metrics[i][k[len(m.name)+1:]].append(v)
    
    if self.case == NOT_DISTRIBUTED_NOT_INCREMENTAL or self.case == NOT_DISTRIBUTED_INCREMENTAL:
      results = {
                'train_metrics': self.epoch_training_metrics,
                'val_metrics': self.epoch_validation_metrics
      }
    elif self.case == DISTRIBUTED_NOT_INCREMENTAL or self.case == DISTRIBUTED_INCREMENTAL:
      results_list = []
      for i in range(len(self.tensorflow_models)):
        results = {
                  'train_metrics': self.epoch_training_metrics[i],
                  'val_metrics': self.epoch_validation_metrics[i]
        }
        results_list.append(results)

    retry = 0
    while not finished and retry < RETRIES:
      try:
        if self.case == NOT_DISTRIBUTED_NOT_INCREMENTAL or self.case == NOT_DISTRIBUTED_INCREMENTAL:
          data = {'data': json.dumps(results)}
          r = requests.post(self.url, data=data)
          if r.status_code == 200:
            finished = True
            logging.info("Metrics updated!")
          else:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            retry += 1
        elif self.case == DISTRIBUTED_NOT_INCREMENTAL or self.case == DISTRIBUTED_INCREMENTAL:
          responses = []
          for (result, url) in zip(results_list, self.url):
            data = {'data': json.dumps(result)}
            r = requests.post(url, data=data)
            responses.append(r.status_code)
          if responses[0] == 200 and len(set(responses)) == 1:
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

  def on_epoch_end(self, epoch, logs=None):
    logging.info("Updating training metrics from epoch {}".format(epoch))
    self.__send_data(logs, False)

  def on_test_end(self, logs=None):
    if self.case == NOT_DISTRIBUTED_INCREMENTAL or self.case == DISTRIBUTED_INCREMENTAL:
      logging.info("Updating validation metrics")
      self.__send_data(logs, True)

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

def load_environment_vars(case):
  """Loads the environment information received from dockers
  boostrap_servers, result_url, result_update_url, control_topic, deployment_id, batch, kwargs_fit,
  stream_timeout, message_poll_timeout, numeratorBatch, denominatorBatch
  Returns:
      boostrap_servers (str): list of boostrap server for the Kafka connection
      result_url (str): URL for downloading the untrained model
      result_id (str): Result ID of the model
      control_topic(str): Control topic
      deployment_id (int): deployment ID of the application
      batch (int): Batch size used for training
      kwargs_fit (:obj:json): JSON with the arguments used for training
      kwargs_val (:obj:json): JSON with the arguments used for validation
      stream_timeout (int): stream timeout to wait for new data
      message_poll_timeout (int): window size to get new data
      numeratorBatch (int): number of batches to take for validation
      denominatorBatch (int): total number of batches for validation
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

  if case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
    result_url = eval(result_url)
    result_id = eval(result_id)
    N = len(result_id)
    optimizer = os.environ.get('OPTIMIZER')
    learning_rate = eval(os.environ.get('LEARNING_RATE'))
    loss = os.environ.get('LOSS')
    metrics = os.environ.get('METRICS')
  
  if case == NOT_DISTRIBUTED_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
    stream_timeout = int(os.environ.get('STREAM_TIMEOUT'))
    message_poll_timeout = int(os.environ.get('MESSAGE_POLL_TIMEOUT'))
    if case == NOT_DISTRIBUTED_INCREMENTAL:
      monitoring_metric = os.environ.get('MONITORING_METRIC')
      change = os.environ.get('CHANGE')
    improvement = eval(os.environ.get('IMPROVEMENT'))
    numeratorBatch = int(os.environ.get('NUMERATOR_BATCH'))
    denominatorBatch = int(os.environ.get('DENOMINATOR_BATCH'))

  if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
    return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix)
  elif case == NOT_DISTRIBUTED_INCREMENTAL:
    return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix, stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch)
  elif case == DISTRIBUTED_NOT_INCREMENTAL:
    return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metrics, batch, kwargs_fit, kwargs_val, confussion_matrix, N)
  elif case == DISTRIBUTED_INCREMENTAL:
    return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metrics, batch, kwargs_fit, kwargs_val, confussion_matrix, stream_timeout, message_poll_timeout, improvement, numeratorBatch, denominatorBatch, N)

def get_train_data(boostrap_servers, kafka_topic, group, decoder):
  """Obtains the data and labels for training from Kafka

    Args:
      boostrap_servers (str): list of boostrap servers for the connection with Kafka
      kafka_topic (str): Kafka topic
      group (str): Kafka group
      decoder(class): decoder to decode the data
    
    Returns:
      train_kafka: training data and labels from Kafka
  """
  logging.info("Starts receiving training data from Kafka servers [%s] with topics [%s]", boostrap_servers,  kafka_topic)
  train_data = kafka_io.KafkaDataset(kafka_topic.split(','), servers=boostrap_servers, group=group, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))
  
  return train_data

def get_online_train_data(boostrap_servers, kafka_topic, group, stream_timeout, message_poll_timeout):
  """Obtains the data and labels incrementally for training from Kafka

    Args:
      boostrap_servers (str): list of boostrap servers for the connection with Kafka
      kafka_topic (str): Kafka topic
      group (str): Kafka group
      stream_timeout (int): stream timeout to wait for new data, if -1 it blocks indefinitely
      message_poll_timeout (int): window size to get new data
    
    Returns:
      online_train_kafka: online training data and labels from Kafka
  """
  logging.info("Starts receiving online training data from Kafka servers [%s] with topics [%s], group [%s], stream_timeout [%d] and message_poll_timeout [%d]", boostrap_servers,  kafka_topic, group, stream_timeout, message_poll_timeout)
  
  online_train_data = tfio.experimental.streaming.KafkaBatchIODataset(
    topics=[kafka_topic],
    group_id=group,
    servers=boostrap_servers,
    stream_timeout=stream_timeout,
    message_poll_timeout=message_poll_timeout,
    configuration=None,
    internal=True
  )
  
  return online_train_data

def saveMetrics(case, model_trained, incremental_validation, tensorflow_models):
  if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == NOT_DISTRIBUTED_INCREMENTAL:
    epoch_training_metrics = {}
    epoch_validation_metrics = {}
  elif case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
    epoch_training_metrics = []
    epoch_validation_metrics = []
            
  if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
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
  elif case == NOT_DISTRIBUTED_INCREMENTAL:
    for k, v in model_trained.history.items():
      try:
        epoch_training_metrics[k].append(v)
      except:
        epoch_training_metrics[k] = v
    if incremental_validation != {}:
      epoch_validation_metrics = incremental_validation
  elif case == DISTRIBUTED_NOT_INCREMENTAL:
    for m in tensorflow_models:
      train_dic = {}
      val_dic = {}
      for k, v in model_trained.history.items():
        if m.name in k:
          if not k.startswith("val_"):
            try:
              train_dic[k[len(m.name)+1:]].append(v)
            except:
              train_dic[k[len(m.name)+1:]] = v
          else:
            try:
              val_dic[k[4+len(m.name)+1:]].append(v)
            except:
              val_dic[k[4+len(m.name)+1:]] = v
      epoch_training_metrics.append(train_dic)
      epoch_validation_metrics.append(val_dic)
  elif case == DISTRIBUTED_INCREMENTAL:
    for m in tensorflow_models:
      train_dic = {}
      for k, v in model_trained.history.items():
        if m.name in k:
          try:
            train_dic[k[len(m.name)+1:]].append(v)
          except:
            train_dic[k[len(m.name)+1:]] = v
      epoch_training_metrics.append(train_dic)
    if incremental_validation != {}:
      incremental_validation.pop('loss')
      for m in tensorflow_models:
        val_dic = {}
        for k in incremental_validation.keys():
          if m.name in k:
            val_dic[k[len(m.name)+1:]] = incremental_validation[k]
        epoch_validation_metrics.append(val_dic)
    else:
      epoch_validation_metrics.append({})

  return epoch_training_metrics, epoch_validation_metrics

def createConfussionMatrix(confussion_matrix, test_size, model, test_dataset, kwargs_val):
  cf_generated = False
  cf_matrix = None
  
  if confussion_matrix and test_size > 0:
    try:
      logging.info("Trying to generate confussion matrix")

      test = model.predict(test_dataset, **kwargs_val)
      """Predicts test data on the trained model"""

      test = np.argmax(test, axis=1)
      """Arg max for each sub list"""
                      
      y_true = np.concatenate([y for _, y in test_dataset], axis=0)

      cf_matrix = confusion_matrix(y_true, test)
      """Generates the confussion matrix"""

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

  return cf_generated, cf_matrix

def sendMetrics(case, model, cf_generated, stream_timeout, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix, result_url, tensorflow_models):
  retry = 0
  finished = False

  datasource_received = False
  start_sending_results = time.time()
  
  while not finished and retry < RETRIES:
    try:
      if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == NOT_DISTRIBUTED_INCREMENTAL:
        model.save(TRAINED_MODEL_PATH)
        """Saves the trained model in the filesystem"""
                  
        files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb'),
                'confussion_matrix': open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}              

        if stream_timeout == -1:
          indefinite = True
        else:
          indefinite = False

        results = {
                'train_metrics': epoch_training_metrics,
                'val_metrics': epoch_validation_metrics,
                'test_metrics': test_metrics,
                'training_time': round(dtime, 4),
                'confusion_matrix': cf_matrix.tolist() if cf_generated else None,
                'indefinite': indefinite
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
      elif case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
        TRAINED_MODEL_PATHS = []
        for i in range (1, N+1):
          path = 'trained_model_{}.h5'.format(i)
          TRAINED_MODEL_PATHS.append(path)

        for m, p in zip(tensorflow_models, TRAINED_MODEL_PATHS):
          m.save(p)
        """Saves the trained models in the filesystem"""

        files = []
        for p in TRAINED_MODEL_PATHS:
          files_dic = {'trained_model': open(p, 'rb'),
                      'confussion_matrix': None} # open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}
          files.append(files_dic)

        if stream_timeout == -1:
          indefinite = True
        else:
          indefinite = False

        results_list = []
        for i in range (N):
          results = {
                    'train_metrics': epoch_training_metrics[i],
                    'val_metrics': epoch_validation_metrics[i],
                    'test_metrics': test_metrics[i] if case == DISTRIBUTED_NOT_INCREMENTAL else [],
                    'training_time': round(dtime, 4),
                    'confusion_matrix': None, # cf_matrix.tolist() if cf_generated else None
                    'indefinite': indefinite
          }
          results_list.append(results)

        responses = []
        for (result, url, f) in zip(results_list, result_url, files):
          data = {'data' : json.dumps(result)}
          logging.info("Sending result data to backend")
          r = requests.post(url, files=f, data=data)
          responses.append(r.status_code)
        """Sends the training results to the backend"""

        if responses[0] == 200 and len(set(responses)) == 1:
          finished = True
          datasource_received = True
          logging.info("Results data sent correctly to backend!!")
        else:
          time.sleep(SLEEP_BETWEEN_REQUESTS)
          retry += 1
    except Exception as e:
      traceback.print_exc()
      retry += 1
      logging.error("Error sending the result to the backend [%s].", str(e))
      time.sleep(SLEEP_BETWEEN_REQUESTS)
  
  end_sending_results = time.time()
  logging.info("Total time sending results: %s", str(end_sending_results - start_sending_results))

  return datasource_received

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

    select_gpu()
    
    gpus = tf.config.experimental.list_physical_devices('GPU')
    for gpu in gpus:
      tf.config.experimental.set_memory_growth(gpu, True)

    case = int(os.environ.get('CASE'))

    if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
      bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix  = load_environment_vars(case)

      logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s])",
              bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, str(kwargs_fit), str(kwargs_val))
    elif case == NOT_DISTRIBUTED_INCREMENTAL:
      bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix, stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch = load_environment_vars(case)

      logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s], [%d], [%d], [%s], [%s], [%s], [%d], [%d])",
              bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, str(kwargs_fit), str(kwargs_val), stream_timeout, message_poll_timeout, monitoring_metric, change, str(improvement), numeratorBatch, denominatorBatch)
    elif case == DISTRIBUTED_NOT_INCREMENTAL:
      bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metrics, batch, kwargs_fit, kwargs_val, confussion_matrix, N = load_environment_vars(case)

      logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metric, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%s], [%s], [%s], [%s], [%d], [%s], [%s])",
              bootstrap_servers, str(result_url), str(result_id), control_topic, deployment_id, optimizer, str(learning_rate), loss, metrics, batch, str(kwargs_fit), str(kwargs_val))
    elif case == DISTRIBUTED_INCREMENTAL:
      bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metrics, batch, kwargs_fit, kwargs_val, confussion_matrix, stream_timeout, message_poll_timeout, improvement, numeratorBatch, denominatorBatch, N = load_environment_vars(case)
      if stream_timeout == -1:
        monitoring_metric = 'loss'
        change = 'down'

      logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, optimizer, learning_rate, loss, metric, batch, kwargs_fit, kwargs_val, stream_timeout, message_poll_timeout, improvement, numeratorBatch, denominatorBatch) ([%s], [%s], [%s], [%s], [%d], [%s], [%s], [%s], [%s], [%d], [%s], [%s], [%d], [%d], [%s], [%d], [%d])",
              bootstrap_servers, str(result_url), str(result_id), control_topic, deployment_id, optimizer, str(learning_rate), loss, metrics, batch, str(kwargs_fit), str(kwargs_val), stream_timeout, message_poll_timeout, str(improvement), numeratorBatch, denominatorBatch)
    """Loads the environment information"""

    if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == NOT_DISTRIBUTED_INCREMENTAL:
      download_model(result_url, PRE_MODEL_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
    
      model = load_model(PRE_MODEL_PATH)
    elif case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
      PRE_MODEL_PATHS = []
      """Paths of the received pre-models"""
      for i, url in enumerate(result_url, start=1):
        path='pre_model_{}.h5'.format(i)
        PRE_MODEL_PATHS.append(path)

        download_model(url, path, RETRIES, SLEEP_BETWEEN_REQUESTS)

      tensorflow_models = []
      for path in PRE_MODEL_PATHS:
        tensorflow_models.append(load_model(path))
    """Downloads the models from the URLs received and saves in the filesystem"""
    """Loads the models from the filesystem to Tensorflow models"""
    
    consumer = KafkaConsumer(control_topic, bootstrap_servers=bootstrap_servers, auto_offset_reset='earliest', enable_auto_commit=False)
    """Starts a Kafka consumer to receive the datasource information from the control topic"""
    
    logging.info("Created and connected Kafka consumer for control topic")
    counter = 0
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
            logging.info("Received control confirmation of data from Kafka for deployment ID %s. Ready to receive data from topic %s with batch %d", deployment_id, str(kafka_topic), batch)
            
            decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
            """Gets the decoder from the information received"""

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
              kafka_dataset = get_train_data(bootstrap_servers, kafka_topic, result_id, decoder)
            elif case == NOT_DISTRIBUTED_INCREMENTAL:
              online_kafka_dataset = get_online_train_data(bootstrap_servers, kafka_topic, result_id, stream_timeout, message_poll_timeout)
            elif case == DISTRIBUTED_NOT_INCREMENTAL:
              kafka_dataset = get_train_data(bootstrap_servers, kafka_topic, str(result_id), decoder)
            elif case == DISTRIBUTED_INCREMENTAL:
              online_kafka_dataset = get_online_train_data(bootstrap_servers, kafka_topic, str(result_id), stream_timeout, message_poll_timeout)
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
                        
            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_NOT_INCREMENTAL:
              training_size = int((1-(data['validation_rate']+data['test_rate']))*(data['total_msg']))
              validation_size = int(data['validation_rate'] * data['total_msg'])
              test_size = int(data['test_rate'] * data['total_msg'])
              logging.info("Training batch size %d, validation batch size %d and test batch size %d", training_size, validation_size, test_size)
            
            start = time.time()

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_NOT_INCREMENTAL:
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

            """Distributed models tensorflow code"""
            if case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
              metrics = metrics.replace(' ', '')
              metrics = metrics.split(',')
              """Formats metrics"""

              outputs = []
              img_input = tensorflow_models[0].input
              outputs.append(tensorflow_models[0](img_input))
              for index in range(1, N):
                next_input = outputs[index-1]
                outputs.append(tensorflow_models[index](next_input[0]))
              """Obteins all the outputs from each distributed submodel"""

              predictions = []
              for index in range(0, N-1):
                s = outputs[index]
                predictions.append(s[1])
              predictions.append(outputs[-1])
              """Obteins all the prediction outputs from each distributed submodel"""

              model = keras.Model(inputs=[img_input], outputs=predictions, name='model')
              """Creates a global model consisting of all distributed submodels"""

              weights = {}
              for m in tensorflow_models:
                weights[m.name] = loss
              """Sets the loss"""

              learning_rates = []
              for index in range (0, N):
                learning_rates.append(learning_rate)
              """Sets the learning rate for each distributed model"""

              model.compile(optimizer=optimizer, loss=weights, metrics=metrics, loss_weights=learning_rates)
              """Compiles the global model"""
            
            if 'tensorflow_models' in globals() or 'tensorflow_models' in locals():
              callback = CustomCallback(result_url, case, tensorflow_models)
            else:
              callback = CustomCallback(result_url, case)

            incremental_validation = {}

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_NOT_INCREMENTAL:
              model_trained = model.fit(train_dataset, validation_data=validation_dataset, **kwargs_fit, callbacks=[callback])
            elif case == NOT_DISTRIBUTED_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
              test_dataset = None
              test_size = 0
              for mini_ds in online_kafka_dataset:
                mini_ds = mini_ds.map(lambda x, y: decoder.decode(x, y)).batch(batch)
                if len(mini_ds) > 0:
                  counter += 1
                  if counter < denominatorBatch - numeratorBatch:
                    model_trained = model.fit(mini_ds, **kwargs_fit, callbacks=[callback])
                  elif counter < denominatorBatch:
                    aux_val = model.evaluate(mini_ds, **kwargs_val, callbacks=[callback])
                    if incremental_validation == {}:
                      for k, i in zip(model_trained.history.keys(), range(len(model_trained.history.keys()))):
                        incremental_validation[k] = [aux_val[i]]
                      if stream_timeout == -1:
                        reference = incremental_validation[monitoring_metric][0]
                    else:
                      for k, i in zip(incremental_validation.keys(), range(len(incremental_validation.keys()))):
                        incremental_validation[k].append(aux_val[i])
                      if stream_timeout == -1:
                        if (change == 'up' and incremental_validation[monitoring_metric][-1] - reference >= improvement) or (change == 'down' and reference - incremental_validation[monitoring_metric][-1] >= improvement):
                          dtime = time.time() - start
                          reference = incremental_validation[monitoring_metric][-1]
                          cf_generated, cf_matrix = createConfussionMatrix(confussion_matrix, test_size, model, test_dataset, kwargs_val)
                          if case == NOT_DISTRIBUTED_INCREMENTAL:
                            epoch_training_metrics, epoch_validation_metrics = saveMetrics(case, model_trained, incremental_validation, None)
                            datasource_received = sendMetrics(case, model, cf_generated, stream_timeout, epoch_training_metrics, epoch_validation_metrics, {}, dtime, cf_matrix, result_url, None)
                          else:
                            epoch_training_metrics, epoch_validation_metrics = saveMetrics(case, model_trained, incremental_validation, tensorflow_models)
                            datasource_received = sendMetrics(case, model, cf_generated, stream_timeout, epoch_training_metrics, epoch_validation_metrics, [], dtime, cf_matrix, result_url, tensorflow_models)
                    if test_dataset == None:
                      test_dataset = mini_ds
                    else:
                      test_dataset = test_dataset.concatenate(mini_ds)
                  elif counter == denominatorBatch:
                    counter = 0
                    model_trained = model.fit(mini_ds, **kwargs_fit, callbacks=[callback])
              if test_dataset != None:
                test_dataset = test_dataset.batch(batch)
                test_size = len(test_dataset)
            """Trains the model"""

            end = time.time()
            logging.info("Total training time: %s", str(end - start))
            logging.info("Model trained! Loss: %s",str(model_trained.history['loss'][-1]))

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == NOT_DISTRIBUTED_INCREMENTAL:
              epoch_training_metrics, epoch_validation_metrics = saveMetrics(case, model_trained, incremental_validation, None)
              test_metrics = {}
            elif case == DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_INCREMENTAL:
              epoch_training_metrics, epoch_validation_metrics = saveMetrics(case, model_trained, incremental_validation, tensorflow_models)
              test_metrics = []

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == DISTRIBUTED_NOT_INCREMENTAL:
              if test_size > 0:
                logging.info("Model ready to test with configuration %s", str(kwargs_val))
                test = model.evaluate(test_dataset, **kwargs_val)
                """Validates the model"""
                logging.info("Model tested!")
                logging.info("Model test metrics: %s", str(test))
              
                if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
                  for k, i in zip(epoch_training_metrics.keys(), range(len(epoch_training_metrics.keys()))):
                    test_metrics[k] = [test[i]]
                elif case == DISTRIBUTED_NOT_INCREMENTAL:
                  for x in range(N):
                    test_dic = {}
                    for k, i in zip(epoch_training_metrics[x].keys(), range(x+1, len(epoch_training_metrics[x].keys())*N+1, N)):
                      test_dic[k] = [test[i]]
                    test_metrics.append(test_dic)

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL or case == NOT_DISTRIBUTED_INCREMENTAL:
              cf_generated, cf_matrix = createConfussionMatrix(confussion_matrix, test_size, model, test_dataset, kwargs_val)
           
            logging.info(f"Training metrics per epoch {epoch_training_metrics}")
            logging.info(f"Validation metrics per epoch {epoch_validation_metrics}")
            logging.info(f"Test metrics {test_metrics}")
            
            dtime = end - start

            if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
              datasource_received = sendMetrics(case, model, cf_generated, None, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix, result_url, None)
            elif case == NOT_DISTRIBUTED_INCREMENTAL:
              datasource_received = sendMetrics(case, model, cf_generated, stream_timeout, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix, result_url, None)
            elif case == DISTRIBUTED_NOT_INCREMENTAL:
              datasource_received = sendMetrics(case, model, None, None, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, None, result_url, tensorflow_models)
            elif case == DISTRIBUTED_INCREMENTAL:
              datasource_received = sendMetrics(case, model, None, stream_timeout, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, None, result_url, tensorflow_models)
      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))
  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))