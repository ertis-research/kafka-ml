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
                              dataset_restrictions=json.dumps(data_res), validation_rate=0.1, control_topic='FEDERATED_DATA_CONTROL_TOPIC',
                              unsupervised_topic='unsupervised_automl')

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()

print("train: ", (x_train.shape, y_train.shape))

x_train_supervised = x_train[:9999]
y_train_supervised = y_train[:9999]

x_train_unsupervised_1 = x_train[10000:19999]
x_train_unsupervised_2 = x_train[20000:29999]
x_train_unsupervised_3 = x_train[30000:39999]
x_train_unsupervised_4 = x_train[40000:49999]
x_train_unsupervised_5 = x_train[50000:59999]

logging.info("Sending initial supervised data...")

# Training data with labels
for (x, y) in zip(x_train_supervised, y_train_supervised):
  mnist.send(data=x, label=y)

# Send online control message to start supervised training
mnist.send_online_control_msg(data=x_train[0], label=y_train[0])

logging.info("Waiting 30 seconds to let worker job start and also let model train with labeled data...")

sleep(30)

logging.info("Sending first part of the unsupervised data...")

# Training data without labels
for x in x_train_unsupervised_1:
  mnist.unsupervised_send(data=x)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending second part of the unsupervised data...")

# Training data without labels
for x in x_train_unsupervised_2:
  mnist.unsupervised_send(data=x)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending third part of the unsupervised data...")

# Training data without labels
for x in x_train_unsupervised_3:
  mnist.unsupervised_send(data=x)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending fourth part of the unsupervised data...")

# Training data without labels
for x in x_train_unsupervised_4:
  mnist.unsupervised_send(data=x)

logging.info("Waiting 100 seconds...")

sleep(100)

logging.info("Sending fifth part of the unsupervised data...")

# Training data without labels
for x in x_train_unsupervised_5:
  mnist.unsupervised_send(data=x)

mnist.online_close()