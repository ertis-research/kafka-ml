from tensorflow import keras
import urllib
import time
import logging
from config import *
import numpy as np

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

def string_to_numpy_type(out_type):
  """Converts a string with the same name to a Numpy type.
  Acceptable types are half, float, double, int32, uint16, uint8, int16, int8, int64, string, bool.
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
  res = np.frombuffer(x, dtype=output_type)
  output_reshape = np.insert(output_reshape, 0, 1, axis=0)
  res = res.reshape(*output_reshape)
  return res