import json
import logging
import os

import tensorflow as tf
from tensorflow import keras
import tensorflow_datasets as tfds
import numpy as np

from flask import Flask, request, Response

gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
print("Num GPUs Available: ", len(tf.config.list_physical_devices('GPU')))

def format_ml_code(code):
    """Checks if the ML code ends with the string 'model = ' in its last line. Otherwise, it adds the string.
        Args:
            code (str): ML code to check
        Returns:
            str: code formatted
    """
    return code[:code.rfind('\n')+1] + 'model = ' + code[code.rfind('\n')+1:]

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
   
    if distributed:
        ml_code = format_ml_code(model_code)
        exec (ml_code, None, globals())
        """Runs the ML code"""
    else:
        exec (model_code, None, globals())

    return model

def get_sample_data(batch):
    x_train_data = np.random.random((batch, 1))
    y_train_data = np.random.random((batch, 1))
    x_test_data  = np.random.random((batch, 1))
    y_test_data  = np.random.random((batch, 1))
    
    ds_train = tf.data.Dataset.from_tensor_slices((x_train_data, y_train_data))
    ds_test = tf.data.Dataset.from_tensor_slices((x_test_data, y_test_data))

    return ds_train, ds_test

def get_sample_model():
    tf_executor_sample_model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(10, activation='relu', input_shape=(1,)),
        tf.keras.layers.Dense(1, activation='softmax'),
    ])
    tf_executor_sample_model.compile(loss='mse', optimizer='rmsprop')

    return tf_executor_sample_model

app = Flask(__name__)    

@app.route('/exec_tf/', methods=['POST'])
def tensorflow_executor():
    try:        
        data = json.loads(request.data)
        logging.info("Data code received %s", data)
        model = exec_model(data['imports_code'], data['model_code'], data['distributed'])

        if data['request_type'] == "check":     
            model.summary()           
            return Response(status=200)
        elif data['request_type'] == 'load_model':
            filename = "model.h5"
            model.save(filename)
            with open(filename, 'rb') as f:
                file_data = f.read()
                f.close()
                response = Response(file_data, status=200)
                if os.path.exists(filename):
                    os.remove(filename)
                    """Removes the temporally file created"""
            return response
        elif data['request_type'] == 'input_shape':
            input_shape = str(model.input_shape)
            return Response(input_shape, status=200)

        return Response(status=404)
    except Exception as e:
        return Response(status=400) 

@app.route('/check_deploy_config/', methods=['POST'])
def check_deploy_config():
    try:        
        data = json.loads(request.data)
        logging.info("Data code received %s", data)

        print(data)
        
        data['kwargs_fit'] = json.loads(data['kwargs_fit'].replace("'", '"'))
        data['kwargs_val'] = json.loads(data['kwargs_val'].replace("'", '"'))

        assert data['kwargs_fit']['epochs'] > 0 and type(data['kwargs_fit']['epochs']) == int
        data['kwargs_fit']['epochs'] = 1
        
        train, test = get_sample_data(data['batch'])
        tf_executor_model = get_sample_model()

        tf_executor_model.fit(train, **data['kwargs_fit'])
        tf_executor_model.evaluate(test, **data['kwargs_val'])

        return Response(status=200)
    except Exception as e:
        print(e)
        return Response(status=400) 
