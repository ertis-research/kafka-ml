import tensorflow as tf
from tensorflow import keras
import urllib
import time
import logging
from config import *
import numpy as np
import sys
import os
import subprocess as sp

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

"""CONSTANTS FOR TYPES OF TRAINING"""
NOT_DISTRIBUTED_NOT_INCREMENTAL = 1
NOT_DISTRIBUTED_INCREMENTAL = 2
DISTRIBUTED_NOT_INCREMENTAL = 3
DISTRIBUTED_INCREMENTAL = 4

def download_model(model_url, filename, retries, sleep_time):
  """Downloads the model from the URL received and saves it in the filesystem
  Args:
      model_url(str): URL of the model 
  """
  finished = False
  retry = 0
  while not finished and retry < retries:
    try:
      filedata = urllib.request.urlopen(model_url)
      datatowrite = filedata.read()
      with open(filename, 'wb') as f:
          f.write(datatowrite)
      finished = True
      logging.info("Downloaded file model from server!")
    except Exception as e:
      retry +=1
      logging.error("Error downloading the model file [%s]", str(e))
      time.sleep(sleep_time)

def string_to_numpy_type(out_type):
    """Converts a string with the same name to a Numpy type.
    Acceptable types are half, float, double, int32, uint16, uint8, 
                int16, int8, int64, string, bool.
    Args:
        out_type (str): Output type to convert
    Returns:
        Numpy DType: Numpy DType of the intput
    """
    if out_type == 'half':
        return np.half
    elif out_type == 'float':
        return np.float
    elif out_type == 'float32':
        return np.float32
    elif out_type == 'double':
        return np.double
    elif out_type == 'int64':
        return np.int64
    elif out_type == 'int32':
        return np.int32
    elif out_type == 'int16':
        return np.int16 
    elif out_type == 'int8':
        return np.int8
    elif out_type == 'uint16':
        return np.uint16 
    elif out_type == 'uint8':
        return np.uint8 
    elif out_type == 'string':
        return np.string
    elif out_type == 'bool':
        return np.bool
    else:
        raise Exception('string_to_numpy_type: Unsupported type')

def load_model(model_path):
  """Returns the model saved previously in the filesystem.
  Args:
    model_path (str): path of the model
  Returns:
    Tensorflow model: tensorflow model loaded
  """
  model = keras.models.load_model(model_path)
  if DEBUG:
    model.summary()
    """Prints model architecture"""
  return model

def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed.
    Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)
    Returns:
        DType: raw data to tensorflow model loaded
    """
    # res = np.frombuffer(x, dtype=output_type)
    # output_reshape = np.insert(output_reshape, 0, 1, axis=0)
    # res = res.reshape(*output_reshape)
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
  y = decode_raw(y, output_type_y, reshape_y)
  return (x, y)

def configure_logging():
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

    gpus = tf.config.experimental.list_physical_devices('GPU')
    for gpu in gpus:
      tf.config.experimental.set_memory_growth(gpu, True)
  except Exception as e:
    print('"nvidia-smi" is probably not installed. GPUs are not masked.', e)

def load_distributed_environment_vars():
    """Loads the distributed environment information received from dockers
    optimizer, learning_rate, loss, metrics
    Returns:
        optimizer (str): optimizer
        learning_rate (decimal): learning rate
        loss (str): loss
        metrics (str): monitoring metrics
    """
    optimizer = os.environ.get('OPTIMIZER')
    learning_rate = eval(os.environ.get('LEARNING_RATE'))
    loss = os.environ.get('LOSS')
    metrics = os.environ.get('METRICS')

    return optimizer, learning_rate, loss, metrics

def load_incremental_environment_vars():
    """Loads the incremental environment information received from dockers
    stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch
    Returns:
        stream_timeout (int): stream timeout to wait for new data
        message_poll_timeout (int): window size to get new data
        monitoring_metric (str): metric to track for indefinite training
        change (str): direction in which monitoring metric improves
        improvement (decimal): how many the monitoring metric improves
        numeratorBatch (int): number of batches to take for validation
        denominatorBatch (int): total number of batches for validation
    """
    stream_timeout = int(os.environ.get('STREAM_TIMEOUT'))
    message_poll_timeout = int(os.environ.get('MESSAGE_POLL_TIMEOUT'))
    monitoring_metric = os.environ.get('MONITORING_METRIC')
    change = os.environ.get('CHANGE')
    improvement = eval(os.environ.get('IMPROVEMENT'))
    numeratorBatch = int(os.environ.get('NUMERATOR_BATCH'))
    denominatorBatch = int(os.environ.get('DENOMINATOR_BATCH'))

    return stream_timeout, message_poll_timeout, monitoring_metric, change, improvement, numeratorBatch, denominatorBatch