import tensorflow as tf
from tensorflow import keras
import urllib
import time
import logging
from config import *

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