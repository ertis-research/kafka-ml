import json
import logging
import os

import tensorflow as tf
from tensorflow import keras
import tensorflow_datasets as tfds
import numpy as np
import time

import tensorflow_io.kafka as kafka_io
from kafka import KafkaConsumer
from decoders import DecoderFactory

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
    



def retrieve_kafka_dataset(model_deployment_id: int, control_topic: str, bootstrap_servers: str, timeout: int = 60):
    consumer = KafkaConsumer(control_topic, bootstrap_servers=bootstrap_servers, auto_offset_reset='earliest', enable_auto_commit=False)
    datasource_received = False

    start_time = time.time()

    while not datasource_received and (time.time() - start_time) < timeout:
        msg = next(consumer)
        try:
            data = None
            if msg.key is not None:
                received_deployment_id = int.from_bytes(msg.key, byteorder='big')
                if received_deployment_id == int(model_deployment_id):

                    data = json.loads(msg.value)
                    """Data received from Kafka control topic. Data is a JSON with this format:
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

                    decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
                    """Gets the decoder from the information received"""

                    kafka_dataset = kafka_io.KafkaDataset(kafka_topic.split(','), servers=bootstrap_servers, group="TF_EXEC", eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))

                    return kafka_dataset

        except Exception as e:
            logging.error("Error decoding message: %s", e)
            raise e
    return tf.data.Dataset.from_tensor_slices([])


def retrieve_representative_dataset(model_deployment_id: int, control_topic: str, bootstrap_servers: str, repr_data_size: int = 100):
    dataset = retrieve_kafka_dataset(model_deployment_id, control_topic, bootstrap_servers)
    for data in dataset.batch(1).take(repr_data_size).map(lambda x, _: x):
        yield [tf.dtypes.cast(data, tf.float32)]


@app.route('/convert_to_tflite/', methods=['POST'])
def convert_to_tflite():
    model_file = None

    # check for .h5 models in files
    for file in request.files:
        if file.endswith('.h5'):
            model_file = request.files[file]
            break
    
    if model_file:
        # Retrieve Quantization parameters from the request
        quantization_params = request.form.to_dict()

        # Parse applyQuantization as a boolean
        quantization_params["applyQuantization"] = quantization_params["applyQuantization"].lower() == 'true'

        # Save the model file to a temporary location
        # Create tmp dir if it doesn't exist not in root
        if not os.path.exists('./tmp'):
            os.makedirs('./tmp')

        model_path = os.path.join('./tmp', model_file.filename)
        model_file.save(model_path)

        # Load the Keras model
        model = tf.keras.models.load_model(model_path)

        
        # Create a TFLite converter
        converter = tf.lite.TFLiteConverter.from_keras_model(model)

        # Apply quantization if specified
        if quantization_params["applyQuantization"]:
            if quantization_params["quantizationType"] == "dynamic":
                converter.optimizations = [tf.lite.Optimize.DEFAULT]
            elif quantization_params["quantizationType"] == "int8":
                converter.optimizations = [tf.lite.Optimize.DEFAULT]
                converter.representative_dataset = lambda: retrieve_representative_dataset(
                                                        quantization_params["modelDeploymentId"],
                                                        quantization_params["dataControlTopic"],
                                                        quantization_params["dataBootstrapServers"]
                                                    )
                converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
                converter.inference_input_type = tf.int8
                converter.inference_output_type = tf.int8

        # Convert model given the quantization parameters
        tflite_model = converter.convert()



        # Save the TFLite model to a file
        tflite_model_path = model_path.replace('.h5', '.tflite')
        with open(tflite_model_path, 'wb') as f:
            f.write(tflite_model)

        # Return the TFLite model file
        with open(tflite_model_path, 'rb') as f:
            tflite_file_data = f.read()

        # Clean up temporary files
        os.remove(model_path)
        os.remove(tflite_model_path)

        return Response(tflite_file_data, mimetype='application/octet-stream', status=200)

    return Response("Invalid file type. Please upload a .h5 file.", status=400)
