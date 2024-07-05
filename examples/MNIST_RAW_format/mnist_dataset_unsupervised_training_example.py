import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.raw_sink import RawSink
import tensorflow as tf
import logging

logging.basicConfig(level=logging.INFO)

mnist = RawSink(boostrap_servers='localhost:9094', topic='automl', deployment_id=1,
        description='Mnist dataset', validation_rate=0.1, test_rate=0.1, unsupervised_topic='unsupervised_automl')

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
print("train: ", (x_train.shape, y_train.shape))

x_train_supervised = x_train[:9999]
y_train_supervised = y_train[:9999]

x_train_unsupervised = x_train[10000:]

# Training data with labels
for (x, y) in zip(x_train_supervised, y_train_supervised):
  mnist.send(data=x, label=y)

# Training data without labels
for x in x_train_unsupervised:
  mnist.unsupervised_send(data=x)

for (x, y) in zip(x_test, y_test):
  mnist.send(data=x, label=y)

mnist.close()