import json
import logging
import os

import tensorflow as tf
from tensorflow import keras
import tensorflow_datasets as tfds
import numpy as np

from flask import Flask, request, Response

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


def normalize_img(image, label):
    """Normalizes images: `uint8` -> `float32`."""
    return tf.cast(image, tf.float32) / 255., label

def get_MNIST_data(batch):
    (ds_train, ds_test), _ = tfds.load(
            'mnist',
            split=['train', 'test'],
            shuffle_files=True,
            as_supervised=True,
            with_info=True,
        )

    ds_train = ds_train.map(
        normalize_img, num_parallel_calls=tf.data.AUTOTUNE)
    ds_train = ds_train.batch(batch)
    ds_train = ds_train.cache()
    ds_train = ds_train.prefetch(tf.data.AUTOTUNE)

    ds_test = ds_test.map(
        normalize_img, num_parallel_calls=tf.data.AUTOTUNE)
    ds_test = ds_test.batch(batch)
    ds_test = ds_test.prefetch(tf.data.AUTOTUNE)

    return ds_train, ds_test

def get_MNIST_model():
    model = tf.keras.models.Sequential([
        tf.keras.layers.Flatten(input_shape=(28, 28)),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(10)
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(0.001),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy()],
    )

    return model

@app.route('/check_deploy_config/', methods=['POST'])
def check_deploy_config():
    try:        
        data = json.loads(request.data)
        logging.info("Data code received %s", data)
        
        data['kwargs_fit'] = json.loads(data['kwargs_fit'].replace("'", '"'))
        data['kwargs_val'] = json.loads(data['kwargs_val'].replace("'", '"'))

        assert data['kwargs_fit']['epochs'] > 0 and type(data['kwargs_fit']['epochs']) == int
        data['kwargs_fit']['epochs'] = 1

        train, test = get_MNIST_data(data['batch'])

        model = get_MNIST_model()
        
        model.fit(train, **data['kwargs_fit'])
        model.evaluate(test, **data['kwargs_val'])

        return Response(status=200)
    except Exception as e:
        return Response(status=400) 
