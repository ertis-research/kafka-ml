import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.federated_raw_sink import FederatedRawSink
import tensorflow as tf
import logging
import json

logging.basicConfig(level=logging.INFO)

with open('mnist_sample_input_format.json') as json_file:
    data_res = json.load(json_file)

mnist = FederatedRawSink(boostrap_servers='localhost:9094', topic='mnist_fed', deployment_id=1, description='Mnist dataset', 
                        dataset_restrictions=json.dumps(data_res), validation_rate=0.1, test_rate=0, control_topic='FEDERATED_DATA_CONTROL_TOPIC')

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()

for (x, y) in zip(x_test, y_test):
    mnist.send(data=x, label=y)

mnist.close()