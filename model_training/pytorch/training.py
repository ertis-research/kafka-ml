__author__ = 'Antonio J. Chaves'

import numpy as np
import torch
from torch import nn
from torch.optim import optimizer
from torch.utils.data import DataLoader
from torchvision.transforms import ToTensor
import torchvision.models as models

from ignite.engine import Engine, Events, create_supervised_trainer, create_supervised_evaluator
from ignite.metrics import *
from ignite.handlers import ModelCheckpoint
from ignite.contrib.handlers import TensorboardLogger, global_step_from_engine

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

from sys import path
path.append('.')
from TrainingKafkaDataset import TrainingKafkaDataset


TRAINED_MODEL_PATH='trained_model.pt'
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

def get_train_data(boostrap_servers, kafka_topic, group, transform):
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
  train_data = TrainingKafkaDataset(kafka_topic, boostrap_servers, group, transform)                              
  
  return train_data

def split_fit_params(fn_kwargs_fit: dict):
  fit_dataloader_list = ["shuffle", "sampler", "batch_sampler", "num_workers", "collate_fn", "pin_memory", "drop_last", "timeout",
                         "worker_init_fn", "multiprocessing_context", "generator", "prefetch_factor", "persistent_workers"]  
  trainer_list = ["non_blocking", "prepare_batch", "output_transform", "deterministic", "amp_mode", "scaler", "gradient_accumulation_steps"]
  fit_run_list = ["max_epochs", "epoch_length"]

  fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs = dict(), dict(), dict()

  for args in list(fn_kwargs_fit.keys()):
    if args in fit_dataloader_list:
      fit_dataloader_kwargs[args]=fn_kwargs_fit[args]
    elif args in trainer_list:
      trainer_kwargs[args]=fn_kwargs_fit[args]
    elif args in fit_run_list:
      fit_run_kwargs[args]=fn_kwargs_fit[args]  
  
  return fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs

def split_val_params(fn_kwargs_val: dict):
  val_dataloader_list = ["shuffle", "sampler", "batch_sampler", "num_workers", "collate_fn", "pin_memory", "drop_last", "timeout",
                         "worker_init_fn", "multiprocessing_context", "generator", "prefetch_factor", "persistent_workers"]  
  validator_list = ["non_blocking", "prepare_batch", "output_transform", "amp_mode"]
  val_run_list = ["max_epochs", "epoch_length"]

  val_dataloader_kwargs, validator_kwargs, val_run_kwargs = dict(), dict(), dict()

  for args in list(fn_kwargs_val.keys()):
    if args in val_dataloader_list:
      val_dataloader_kwargs[args]=fn_kwargs_val[args]
    elif args in validator_list:
      validator_kwargs[args]=fn_kwargs_val[args]
    elif args in val_run_list:
      val_run_kwargs[args]=fn_kwargs_val[args]  
  
  return val_dataloader_kwargs, validator_kwargs, val_run_kwargs

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

    bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val  = load_environment_vars()
    """Loads the environment information"""

    logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s])", 
              bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, str(kwargs_fit), str(kwargs_val))
    
    model = download_model(result_url, RETRIES, SLEEP_BETWEEN_REQUESTS)
    """Downloads the model from the URL received to a PyTorch model"""
        
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
            
            kafka_dataset = get_train_data(bootstrap_servers, data, result_id, ToTensor())
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
            
            training_size = int((1-data['validation_rate'])*(data['total_msg']))
            validation_size= (data['total_msg'])-training_size
            logging.info("Training batch size %d and validation batch size %d", training_size, validation_size)
            
            start = time.time()
            train_dataset, validation_dataset = torch.utils.data.random_split(kafka_dataset, [training_size, validation_size])
            """Splits dataset for training and validation"""
            
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            model.to(device)

            logging.info("Splitting done, training is going to start.")

            fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs   = split_fit_params(kwargs_fit)
            val_dataloader_kwargs, validator_kwargs, val_run_kwargs = split_val_params(kwargs_val)
            
            train_dataloader = DataLoader(train_dataset, batch_size=batch, **fit_dataloader_kwargs) # si eso poder psar args extra en el dataloader
            test_dataloader  = DataLoader(validation_dataset, batch_size=batch, **val_dataloader_kwargs)
            
            trainer = create_supervised_trainer(model, model.optimizer(), model.loss_fn(), device, **trainer_kwargs)                    
            train_evaluator = create_supervised_evaluator(model, metrics=model.metrics(), device=device, **validator_kwargs)  
            
            @trainer.on(Events.EPOCH_COMPLETED)
            def log_training_results(trainer):
                train_evaluator.run(train_dataloader, **val_run_kwargs)
                metrics = train_evaluator.state.metrics
                print(f"Training Results - Epoch[{trainer.state.epoch}] Avg sel. metrics: {metrics}")              
                
            trainer.run(train_dataloader, **fit_run_kwargs)
          
            train_evaluator.run(train_dataloader, **val_run_kwargs)
            train_mtrs = train_evaluator.state.metrics
            print(train_mtrs)

            end = time.time()
            logging.info("Total training time: %s", str(end - start))            
            logging.info("Model trainned! Loss: %s",str(train_mtrs['loss']))

            if validation_size > 0:
              logging.info("Model ready to evaluation with configuration %s", str(kwargs_val))

              val_evaluator = create_supervised_evaluator(model, metrics=model.metrics(), device=device, **validator_kwargs)
              val_evaluator.run(test_dataloader, **val_run_kwargs)

              val_mtrs = val_evaluator.state.metrics
              print(val_mtrs)

              """Validates the model"""
              logging.info("Model evaluated!")

            retry = 0
            finished = False
            
            metrics_dic = {}
            train_metrics = ""
            for key in train_mtrs.keys():
              if key!='loss':
                metrics_dic[key] = train_mtrs[key]
                train_metrics += key+": "+str(round(train_mtrs[key],10))+"\n"
            """Get all metrics except the loss"""

            while not finished and retry < RETRIES:
              try:
                torch.save(model.state_dict(), TRAINED_MODEL_PATH)
                """Saves the trained model in the filesystem"""            
                    
                files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb')}

                results = {
                        'train_loss': round(train_mtrs['loss'],10),
                        'train_metrics':  train_metrics,
                }
                if validation_size > 0:
                  """if validation has been defined"""
                  results['val_loss'] = round(val_mtrs['loss'], 10) # Loss is in the first element
                  results['val_metrics'] =''
                  index = 1
                  for key in val_mtrs.keys():
                    if key!='loss':
                      results['val_metrics']+=key+": "+str(round(val_mtrs[key], 10))+"\n"

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

