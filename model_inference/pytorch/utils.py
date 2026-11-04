import torch
from torch import nn
from ignite.metrics import *
import os
import urllib
import time
import logging
import requests
import json
import numpy as np
import torchvision.models as models
from torchvision.transforms import ToTensor

from torch.utils import data
from config import *

def download_model(model_url, retries, sleep_time):
  """Downloads the model from the URL received and saves it in the filesystem
  Args:
      model_url(str): URL of the model 
  """
  finished = False
  retry = 0
  while not finished and retry < retries:
    try:
      
      datatowrite = requests.get(model_url).content.decode("utf-8")
      
      datatowrite = datatowrite.replace("pretrained=True", "pretrained=False")
            
      print(datatowrite)
      exec(datatowrite, None, globals())

      if DEBUG:
        print(model)

      finished = True
      logging.info("Downloaded file model from server!")

      return model
    except Exception as e:
      retry +=1
      logging.error("Error getting the model from backend [%s]", str(e))
      time.sleep(sleep_time)

def download_weights(weights_url, filename, retries, sleep_time):
  """Downloads the model from the URL received and saves it in the filesystem
  Args:
      model_url(str): URL of the model 
  """
  finished = False
  retry = 0
  while not finished and retry < retries:
    try:
      filedata = urllib.request.urlopen(weights_url)
      datatowrite = filedata.read()
      with open(filename, 'wb') as f:
          f.write(datatowrite)
      finished = True
      logging.info("Downloaded model weights from server!")
    except Exception as e:
      retry +=1
      logging.error("Error downloading the model weights [%s]", str(e))
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

def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed, as the training does.

        Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)

        Returns:
        ndarray: sample with the shape received in reshape, without the batch dimension
    """
    res = np.copy(np.frombuffer(x, dtype=output_type))
    if output_reshape is not None and len(output_reshape) > 0:
        res = res.reshape(*output_reshape)
    return res

def sample_to_tensor(sample):
    """Converts a decoded sample to the input of the model with the same transformation used for training
    (ToTensor for samples with 2 or more dimensions, such as images) and adds the batch dimension.

        Args:
        sample (ndarray): decoded sample

        Returns:
        Tensor: batch with the sample
    """
    tensor = ToTensor()(sample) if sample.ndim >= 2 else torch.from_numpy(sample)
    return torch.unsqueeze(tensor, 0)