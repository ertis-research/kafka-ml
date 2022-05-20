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