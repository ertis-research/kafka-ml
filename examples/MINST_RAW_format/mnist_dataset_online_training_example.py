import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.online_raw_sink import OnlineRawSink
import tensorflow as tf
from time import sleep
import logging

logging.basicConfig(level=logging.INFO)

mnist = OnlineRawSink(boostrap_servers='127.0.0.1:9094', topic='automl', deployment_id=1,
        description='Mnist dataset', validation_rate=0.1)

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
print("train: ", (x_train.shape, y_train.shape))

x_train_1 = x_train[:19999]
y_train_1 = y_train[:19999]

x_train_2 = x_train[20000:39999]
y_train_2 = y_train[20000:39999]

x_train_3 = x_train[40000:]
y_train_3 = y_train[40000:]

logging.info("Sending first part of the data...")

for (x, y) in zip(x_train_1, y_train_1):
  mnist.send(data=x, label=y)

logging.info("Waiting 30 seconds...")

sleep(30)

logging.info("Sending second part of the data...")

for (x, y) in zip(x_train_2, y_train_2):
  mnist.send(data=x, label=y)

logging.info("Waiting 30 seconds...")

sleep(30)

logging.info("Sending third part of the data...")

for (x, y) in zip(x_train_3, y_train_3):
  mnist.send(data=x, label=y)

mnist.online_close()