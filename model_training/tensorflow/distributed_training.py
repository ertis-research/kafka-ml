import numpy as np
import tensorflow as tf
from tensorflow import keras
import tensorflow_io.kafka as kafka_io

from kafka import KafkaConsumer

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
from decoders import *

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
    """Loads the environment information received from dockers
    boostrap_servers, result_url, result_update_url, control_topic, deployment_id, batch, kwargs_fit 
    Returns:
        boostrap_servers (str): list of boostrap server for the Kafka connection
        result_url (str): URL for downloading the pre model
        result_id (str): Result ID of the model
        control_topic(str): Control topic
        deployment_id (int): deployment ID of the application
        batch (int): Batch size used for training
        kwargs_fit (:obj:json): JSON with the arguments used for training
        kwargs_val (:obj:json): JSON with the arguments used for validation
    """

    bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
    result_url = eval(os.environ.get('RESULT_URL'))
    result_id = eval(os.environ.get('RESULT_ID'))
    N = len(result_id)
    control_topic = os.environ.get('CONTROL_TOPIC')
    deployment_id = int(os.environ.get('DEPLOYMENT_ID'))
    batch = int(os.environ.get('BATCH'))
    kwargs_fit = json.loads(os.environ.get('KWARGS_FIT').replace("'", '"'))
    kwargs_val = json.loads(os.environ.get('KWARGS_VAL').replace("'", '"'))
    confussion_matrix = json.loads(os.environ.get('CONF_MAT_CONFIG').replace("'", '"'))

    return (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, N, confussion_matrix)

def get_train_data(boostrap_servers, kafka_topic, group, batch, decoder):
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
    train_data = kafka_io.KafkaDataset([kafka_topic], servers=boostrap_servers, group=group, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))
    
    return train_data

if __name__ == "__main__":
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

        gpus = tf.config.experimental.list_physical_devices('GPU')
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)

        start_consuming_data = time.time()

        bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val, N, confussion_matrix = load_environment_vars()
        """Loads the environment information"""

        logging.info("Received environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s])", 
              bootstrap_servers, str(result_url), str(result_id), control_topic, deployment_id, batch, str(kwargs_fit), str(kwargs_val))

        PRE_MODEL_PATHS = []
        '''Paths of the received pre-models'''
        for i, url in enumerate(result_url, start=1):
            path='pre_model_{}.h5'.format(i)
            PRE_MODEL_PATHS.append(path)

            download_model(url, path, RETRIES, SLEEP_BETWEEN_REQUESTS)
            """Downloads the model from the URL received and saves in the filesystem"""

        tensorflow_models = []
        for path in PRE_MODEL_PATHS:
            tensorflow_models.append(load_model(path))
            """Loads the model from the filesystem to a Tensorflow model"""

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
                        
                        decoder = DecoderFactory.get_decoder(data['input_format'], data['input_config'])
                        """Gets the decoder from the information received"""

                        kafka_dataset = get_train_data(bootstrap_servers, kafka_topic, str(result_id), batch, decoder)
                        """Gets the dataset from kafka"""

                        end_consuming_data = time.time()
                        logging.info("Total time consuming data: %s", str(end_consuming_data - start_consuming_data))

                        logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
                        
                        logging.info("Model ready to be trained with configuration %s", str(kwargs_fit))
                        
                        training_size = int((1-(data['validation_rate']+data['test_rate']))*(data['total_msg']))
                        validation_size= int( data['validation_rate'] * data['total_msg'])
                        test_size= int( data['test_rate'] * data['total_msg'])

                        logging.info("Training batch size %d, validation batch size %d and test batch size %d", training_size, validation_size, test_size)
                        
                        start_training = time.time()

                        train_dataset = kafka_dataset.take(training_size).batch(batch)
                        """Splits dataset for training"""

                        test_dataset = kafka_dataset.skip(training_size)

                        if validation_size > 0 and test_size > 0:
                            """If validation and test size are greater than 0, then split the dataset for validation and test"""
                            validation_dataset = test_dataset.skip(test_size).batch(batch)
                            test_dataset = test_dataset.take(test_size).batch(batch)
                        elif validation_size > 0:
                            """If only validation size is greater than 0, then split the dataset for validation"""
                            validation_dataset = test_dataset.batch(batch)
                            test_dataset = None
                        elif test_size > 0:
                            """If only test size is greater than 0, then split the dataset for test"""
                            validation_dataset = None
                            test_dataset = test_dataset.batch(batch)
                        else:
                            """If no validation or test size is greater than 0, then split the dataset for training"""
                            validation_dataset = None
                            test_dataset = None
                        
                        logging.info("Splitting done, training is going to start.")

                        """TENSORFLOW code goes here"""
                        outputs = []
                        img_input = tensorflow_models[0].input
                        outputs.append(tensorflow_models[0](img_input))
                        for index in range(1, N):
                            next_input = outputs[index-1]
                            outputs.append(tensorflow_models[index](next_input[0]))
                            """Obteins all the outputs from each distributed submodel"""

                        predictions = []
                        for index in range(0, N-1):
                            s = outputs[index]
                            predictions.append(s[1])
                        predictions.append(outputs[-1])
                        """Obteins all the prediction outputs from each distributed submodel"""

                        model = keras.Model(inputs=[img_input], outputs=predictions, name='model')
                        """Creates a global model consisting of all distributed submodels"""

                        weights = {}
                        for m in tensorflow_models:
                            weights[m.name] = 'sparse_categorical_crossentropy'
                            """Sets the format of true labels"""

                        learning_rates = []
                        for index in range (0, N):
                            learning_rates.append(0.001)
                            """Sets the value 0.001 as the learning rate from each distributed model"""

                        model.compile(optimizer='adam', loss=weights, metrics=['accuracy'], loss_weights=learning_rates)
                        """Compiles the global model"""

                        model_trained = model.fit(train_dataset, validation_data=validation_dataset, **kwargs_fit)
                        """Trains the model"""

                        logging.info("Model trained history: %s", str(model_trained.history))

                        end_training = time.time()
                        logging.info("Total training time: %s", str(end_training - start_training))

                        epoch_training_metrics   = []
                        epoch_validation_metrics = []
                        test_metrics = []

                        for m in tensorflow_models:
                            train_dic = {}
                            val_dic = {}
                            for k, v in model_trained.history.items():
                                if m.name in k:
                                    if not k.startswith("val_"):
                                        try:
                                            train_dic[k[len(m.name)+1:]].append(v)
                                        except:
                                            train_dic[k[len(m.name)+1:]] = v
                                    else:
                                        try:
                                            val_dic[k[4+len(m.name)+1:]].append(v)
                                        except:
                                            val_dic[k[4+len(m.name)+1:]] = v
                            epoch_training_metrics.append(train_dic)
                            epoch_validation_metrics.append(val_dic)

                        if test_size > 0:
                            logging.info("Model ready to test with configuration %s", str(kwargs_val))
                            evaluation = model.evaluate(test_dataset, **kwargs_val)
                            """Validates the model"""
                            logging.info("Model evaluation: %s", str(evaluation))
                            logging.info("Models evaluated!")
                            
                            for x in range(N):
                                test_dic = {}
                                for k, i in zip(epoch_training_metrics[x].keys(), range(x+1, len(epoch_training_metrics[x].keys())*N+1, N )) :
                                    test_dic[k] = [evaluation[i]]
                                test_metrics.append(test_dic)

                            logging.info("Model test metrics: %s", str(evaluation))


                        retry = 0
                        finished = False

                        start_sending_results = time.time()

                        logging.info(f"Training metrics per epoch {epoch_training_metrics}")
                        logging.info(f"Validation metrics per epoch {epoch_validation_metrics}")
                        logging.info(f"Test metrics {test_metrics}")

                        while not finished and retry < RETRIES:
                            try:
                                TRAINED_MODEL_PATHS = []
                                for i in range (1, N+1):
                                    path = 'trained_model_{}.h5'.format(i)
                                    TRAINED_MODEL_PATHS.append(path)

                                for m, p in zip(tensorflow_models, TRAINED_MODEL_PATHS):
                                    m.save(p)
                                    """Saves the trained models in the filesystem"""

                                files = []
                                for p in TRAINED_MODEL_PATHS:
                                    files_dic = {'trained_model': open(p, 'rb'),
                                                 'confussion_matrix': None} #  open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}
                                    files.append(files_dic)


                                results_list = []
                                for i in range (0, N):
                                    results = {
                                            'train_metrics':  epoch_training_metrics[i],
                                            'val_metrics':  epoch_validation_metrics[i],
                                            'test_metrics':  test_metrics[i],
                                            'training_time': round(end_training - start_training, 4),
                                            'confusion_matrix': None # cf_matrix.tolist() if cf_generated else None
                                    }
                                    results_list.append(results)


                                responses = []
                                for (result, url, f) in zip(results_list, result_url, files):
                                    data = {'data' : json.dumps(result)}
                                    logging.info("Sending result data to backend")
                                    r = requests.post(url, files=f, data=data)
                                    responses.append(r.status_code)
                                    """Sends the training results to the backend"""

                                if responses[0] == 200 and len(set(responses)) == 1:
                                    finished = True
                                    datasource_received = True
                                    logging.info("Results data sent correctly to backend!!")
                                else:
                                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                                    retry+=1
                            except Exception as e:
                                traceback.print_exc()
                                retry+=1
                                logging.error("Error sending the results to the backend [%s].", str(e))
                                time.sleep(SLEEP_BETWEEN_REQUESTS)
                            consumer.close(autocommit=True)
                        end_sending_results = time.time()
                        logging.info("Total time sending results: %s", str(end_sending_results - start_sending_results))
            except Exception as e:
                traceback.print_exc()
                logging.error("Error with the received datasource [%s]. Waiting for new data.", str(e))       
    except Exception as e:
        traceback.print_exc()
        logging.error("Error in main [%s]. Service will be restarted.", str(e))