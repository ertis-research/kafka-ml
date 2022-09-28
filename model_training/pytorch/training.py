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

from sys import path
path.append('.')
from TrainingKafkaDataset import TrainingKafkaDataset


TRAINED_MODEL_PATH = 'trained_model.pt'
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

def get_train_data(boostrap_servers, kafka_topic, group, transform=None):
  """Obtains the data and labels for training from Kafka

    Args:
      boostrap_servers (str): list of boostrap servers for the connection with Kafka
      kafka_topic (str): Kafka topic (out_type_x, out_type_y, reshape_x, reshape_y) (raw): input data
      group (str): Kafka group_id
      transform(class): data transform
    
    Returns:
      train_data: training data and labels from Kafka
  """
  logging.info("Starts receiving training data from Kafka servers [%s] with topics [%s]", boostrap_servers,  kafka_topic)
  train_data = TrainingKafkaDataset(kafka_topic, boostrap_servers, group, transform)                              
  
  return train_data

def split_fit_params(fn_kwargs_fit: dict):
  fit_dataloader_list = ["shuffle", "sampler", "batch_sampler", "num_workers", "collate_fn", "pin_memory", "drop_last", "timeout",
                         "worker_init_fn", "multiprocessing_context", "generator", "prefetch_factor", "persistent_workers"]  
  trainer_list = ["non_blocking", "prepare_batch", "deterministic", "amp_mode", "scaler", "gradient_accumulation_steps"] # "output_transform"
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
  validator_list = ["non_blocking", "prepare_batch", "amp_mode"] # "output_transform"
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

def custom_output_transform(x, y, y_pred, loss):
    return {
        "y": y,
        "y_pred": y_pred,
        "criterion_kwargs": {}
    }

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

    bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, confussion_matrix  = load_environment_vars()
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
            
            kafka_dataset = get_train_data(bootstrap_servers, data, result_id, ToTensor() if len(data['input_config']['data_reshape'].split()) >= 2 else None)
            """Gets the dataset from kafka"""

            logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
            
            training_size = int((1-(data['validation_rate']+data['test_rate']))*(data['total_msg']))
            validation_size= int( data['validation_rate'] * data['total_msg'] )
            test_size= int( data['test_rate'] * data['total_msg'] )

            logging.info("Training subdataset size %d, validation subdataset size %d, and test subdataset size, %d", training_size, validation_size, test_size)
            
            start = time.time()
            diff = data['total_msg'] - (training_size + validation_size + test_size)


            train_dataset, validation_dataset, test_dataset = torch.utils.data.random_split(kafka_dataset, [training_size+diff, validation_size, test_size])
            """Splits dataset for training and validation"""
            
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            model.to(device)

            logging.info("Splitting done, training is going to start.")

            fit_dataloader_kwargs, trainer_kwargs, fit_run_kwargs   = split_fit_params(kwargs_fit)
            val_dataloader_kwargs, validator_kwargs, val_run_kwargs = split_val_params(kwargs_val)
            
            train_dataloader = DataLoader(train_dataset, batch_size=batch, **fit_dataloader_kwargs)

            if validation_size > 0:
              val_dataloader   = DataLoader(validation_dataset, batch_size=batch, **val_dataloader_kwargs)

            if test_size > 0:
              test_dataloader  = DataLoader(test_dataset, batch_size=batch, **val_dataloader_kwargs)
            
            epoch_training_metrics   = {}
            epoch_validation_metrics = {}
            test_metrics = {}

            trainer = create_supervised_trainer(model, model.optimizer(), model.loss_fn(), device, output_transform=custom_output_transform,  **trainer_kwargs) 

            if validation_size > 0:                   
              evaluator = create_supervised_evaluator(model, metrics=model.metrics(), device=device, **validator_kwargs)  

            for name, metric in model.metrics().items():
              metric.attach(trainer, name)

            def save_metrics(engine_metrics_items, epochs_metric_dict):
              for k, v in engine_metrics_items:
                try:
                  epochs_metric_dict[k].append(v)
                except:
                  epochs_metric_dict[k] = [v]
            
            def send_epoch_metrics(res):
              retry = 0
              finished = False
              while not finished and retry < RETRIES:
                try:
                  data = {'data': json.dumps(res)}
                  url = result_url.replace('results', 'results_metrics')
                  r = requests.post(url, data=data)
                  if r.status_code == 200:
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

            @trainer.on(Events.EPOCH_COMPLETED)
            def get_training_metrics(engine):    
              save_metrics(engine.state.metrics.copy().items(), epoch_training_metrics)
              if validation_size > 0: evaluator.run(val_dataloader)

              results = {
                'train_metrics': epoch_training_metrics,
                'val_metrics': epoch_validation_metrics
              }    
              send_epoch_metrics(results)

            if validation_size > 0:        
              @evaluator.on(Events.COMPLETED)
              def get_evaluation_metrics(engine):    
                save_metrics(engine.state.metrics.copy().items(), epoch_validation_metrics)
            
            
            trainer.run(train_dataloader, **fit_run_kwargs)     

            end = time.time()

            if test_size > 0:
              tester = create_supervised_evaluator(model, metrics=model.metrics(), device=device, **validator_kwargs)

              @tester.on(Events.COMPLETED)
              def get_evaluation_metrics(engine):    
                save_metrics(engine.state.metrics.copy().items(), test_metrics)                
              
              tester.run(test_dataloader)  
      
            logging.info("Total training time: %s", str(end - start))            
            logging.info("Model trained! Loss: %s",str(epoch_training_metrics['loss']))

            cf_generated = False
            cf_matrix = None
            if confussion_matrix and test_size > 0:
              try:
                logging.info("Trying to generate confussion matrix")

                model.eval()
                with torch.no_grad():
                  y_pred = []
                  y_true = []
                  for data, target in test_dataloader:
                    data, target = data.to(device), target.to(device)
                    output = model(data)
                    y_pred.append(output.argmax(dim=1).cpu())
                    y_true.append(target.cpu())
                  y_pred = torch.cat(y_pred)
                  y_true = torch.cat(y_true)
                    
                  cf_matrix = confusion_matrix(y_true, y_pred)
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
                torch.save(model.state_dict(), TRAINED_MODEL_PATH)
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

