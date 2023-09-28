import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.federated_online_raw_sink import OnlineFederatedRawSink
import tensorflow as tf
from time import sleep
import logging
import json

logging.basicConfig(level=logging.INFO)

with open('mnist_sample_input_format.json') as json_file:
  data_res = json.load(json_file)

mnist = OnlineFederatedRawSink(boostrap_servers='localhost:9094', topic='mnist_fed', deployment_id=1, description='Mnist dataset', 
                        dataset_restrictions=json.dumps(data_res), validation_rate=0.1, control_topic='FEDERATED_DATA_CONTROL_TOPIC')

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()

mnist.send_online_control_msg(data=x_train[0], label=y_train[0])

print("train: ", (x_train.shape, y_train.shape))

x_train_1 = x_train[:9999]
y_train_1 = y_train[:9999]

x_train_2 = x_train[10000:19999]
y_train_2 = y_train[10000:19999]

x_train_3 = x_train[20000:29999]
y_train_3 = y_train[20000:29999]

x_train_4 = x_train[30000:39999]
y_train_4 = y_train[30000:39999]

x_train_5 = x_train[40000:49999]
y_train_5 = y_train[40000:49999]

x_train_6 = x_train[50000:]
y_train_6 = y_train[50000:]

logging.info("Waiting worker job to start...")

sleep(15)

logging.info("Sending first part of the data...")

for (x, y) in zip(x_train_1, y_train_1):
  mnist.send(data=x, label=y)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending second part of the data...")

for (x, y) in zip(x_train_2, y_train_2):
  mnist.send(data=x, label=y)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending third part of the data...")

for (x, y) in zip(x_train_3, y_train_3):
  mnist.send(data=x, label=y)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending fourth part of the data...")

for (x, y) in zip(x_train_4, y_train_4):
  mnist.send(data=x, label=y)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending fifth part of the data...")

for (x, y) in zip(x_train_5, y_train_5):
  mnist.send(data=x, label=y)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending sixth part of the data...")

for (x, y) in zip(x_train_6, y_train_6):
  mnist.send(data=x, label=y)

mnist.online_close()