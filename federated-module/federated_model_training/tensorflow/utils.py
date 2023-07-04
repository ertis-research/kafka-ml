import tensorflow as tf
import os
import subprocess as sp
import json
import logging
import sys
from config import *
import numpy as np

"""CONSTANTS FOR TYPES OF TRAINING"""
FEDERATED_NOT_DISTRIBUTED_NOT_INCREMENTAL = 1

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

def load_federated_classic_environment_vars():
  """Loads the environment information received from dockers
  kml_cloud_bootstrap_server, data_bootstrap_server, federated_model_id,
  input_data_topic,input_format, input_config, validation_rate, test_rate, total_msg
  Returns:
    kml_cloud_bootstrap_server (str): Kafka bootstrap server for KML Cloud
    data_bootstrap_server (str): Kafka bootstrap server for data
    federated_model_id (str): Federated model ID
    input_data_topic (str): Input data topic
    input_format (str): Input data format
    input_config (dict): Input data configuration
    validation_rate (float): Validation rate
    test_rate (float): Test rate
    total_msg (int): Total number of messages
  """  

  kml_cloud_bootstrap_server = os.environ.get('KML_CLOUD_BOOTSTRAP_SERVERS')
  data_bootstrap_server = os.environ.get('DATA_BOOTSTRAP_SERVERS')

  federated_model_id = os.environ.get('FEDERATED_MODEL_ID')

  input_data_topic = os.environ.get('DATA_TOPIC')
  input_format = os.environ.get('INPUT_FORMAT')
  input_config = json.loads(os.environ.get('INPUT_CONFIG'))

  validation_rate = float(os.environ.get('VALIDATION_RATE'))
  total_msg = int(os.environ.get('TOTAL_MSG'))

  return (kml_cloud_bootstrap_server, data_bootstrap_server, federated_model_id, input_data_topic, input_format, input_config, validation_rate, total_msg)
