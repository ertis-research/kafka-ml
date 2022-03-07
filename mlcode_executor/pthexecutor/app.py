import json
import logging
import os

import numpy as np

import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader
from torchinfo import summary
from torchvision.transforms import ToTensor
import torchvision.models as models

from ignite.metrics import *
from ignite.engine import create_supervised_trainer, create_supervised_evaluator

from flask import Flask, request, Response

def exec_model(imports_code, model_code, distributed):
    """Runs the ML code and returns the generated model
        Args:
            imports_code (str): Imports before the code 
            model_code (str): ML code to run
        Returns:
            model: generated model from the code
    """

    if imports_code is not None and imports_code!='':
        """Checks if there is any import to be executed before the code"""
        exec (imports_code, None, globals())
   
    exec (model_code, None, globals())

    return model

app = Flask(__name__)

@app.route('/exec_pth/', methods=['POST'])
def pytorch_executor():
    try:        
        data = json.loads(request.data)
        logging.info("Data code received %s", data)
        
        # Remove pretrained=True
        data['model_code'] = data['model_code'].replace("pretrained=True", "pretrained=False")
        model = exec_model(data['imports_code'], data['model_code'], data['distributed'])

        if data['request_type'] == "check":
            summary(model)  
            
            # Some checks to ensure the model is well defined for Kafka-ML
            print(model.loss_fn())
            print(model.optimizer())            
            print(model.metrics())
            
            print(type(model.metrics()["loss"]._loss_fn) == type(model.loss_fn()))

            return Response(status=200)    
        elif data['request_type'] == 'input_shape':
            # TODO: https://stackoverflow.com/questions/66488807/pytorch-model-input-shape ??
            input_shape = next(model.parameters()).size()
            return Response(input_shape, status=200)
            
        return Response(status=404)
    except Exception as e:
        return Response(status=400) 

def get_sample_data(batch):
    x_train_data = ToTensor()(np.random.random((batch, 1)))
    y_train_data = ToTensor()(np.random.random((batch, 1)))
    x_test_data  = ToTensor()(np.random.random((batch, 1)))
    y_test_data  = ToTensor()(np.random.random((batch, 1)))
  
    ds_train = TensorDataset(x_train_data, y_train_data)
    ds_test  = TensorDataset(x_test_data , y_test_data )

    train_dataloader = DataLoader(ds_train, batch_size=batch)
    test_dataloader  = DataLoader(ds_test, batch_size=batch)

    return train_dataloader, test_dataloader

def get_sample_model():
    class SampleNeuralNetwork(nn.Module):
        def __init__(self):
            super(SampleNeuralNetwork, self).__init__()
            self.samplelayer = nn.Sequential(
                nn.Linear(1, 10),
                nn.Linear(10, 1),
                nn.Softmax(1)
            )

        def forward(self, x):
            logits = self.samplelayer(x)
            return logits

        def loss_fn(self):
            return nn.MSELoss()

        def optimizer(self):
            return torch.optim.RMSprop(tf_executor_sample_model.parameters())

        def metrics(self):
            val_metrics = {
                "loss": Loss(self.loss_fn())
            }
            return val_metrics

    tf_executor_sample_model = SampleNeuralNetwork()

    return tf_executor_sample_model

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


@app.route('/check_deploy_config/', methods=['POST'])
def check_deploy_config():
    try:        
        data = json.loads(request.data)
        logging.info("Data code received %s", data)

        print("Data Received",data)
        
        data['kwargs_fit'] = json.loads(data['kwargs_fit'].replace("'", '"'))
        data['kwargs_val'] = json.loads(data['kwargs_val'].replace("'", '"'))

        print("Data parsed to json",data)

        assert data['kwargs_fit']['max_epochs'] > 0 and type(data['kwargs_fit']['max_epochs']) == int
        data['kwargs_fit']['max_epochs'] = 1
        
        
        _, trainer_kwargs, fit_run_kwargs   = split_fit_params(data['kwargs_fit'])
        _, validator_kwargs, val_run_kwargs = split_val_params(data['kwargs_val'])

        train, test = get_sample_data(data['batch'])
        tf_executor_model = get_sample_model().double()

        trainer = create_supervised_trainer(tf_executor_model, tf_executor_model.optimizer(), tf_executor_model.loss_fn(), "cpu", **trainer_kwargs)                    
        train_evaluator = create_supervised_evaluator(tf_executor_model, metrics=tf_executor_model.metrics(), device="cpu", **validator_kwargs)

        trainer.run(train, **fit_run_kwargs)
        train_evaluator.run(train, **val_run_kwargs)

        val_evaluator = create_supervised_evaluator(tf_executor_model, metrics=tf_executor_model.metrics(), device="cpu", **validator_kwargs)
        val_evaluator.run(test, **val_run_kwargs)

        return Response(status=200)
    except Exception as e:
        print(e)
        return Response(status=400) 
