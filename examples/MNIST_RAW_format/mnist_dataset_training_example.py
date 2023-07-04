import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.raw_sink import  RawSink
import tensorflow as tf
import logging

logging.basicConfig(level=logging.INFO)

# mnist = RawSink(boostrap_servers='127.0.0.1:9094', topic='automl', deployment_id=1,
#         description='Mnist dataset', validation_rate=0.1, test_rate=0.1,
#         data_type='uint8', label_type='uint8', data_reshape='28 28')

mnist = RawSink(boostrap_servers='localhost:9094', topic='automl', deployment_id=1,
        description='Mnist dataset', validation_rate=0.1, test_rate=0.1)

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
print("train: ", (x_train.shape, y_train.shape))

for (x, y) in zip(x_train, y_train):
  mnist.send(data=x, label=y)

for (x, y) in zip(x_test, y_test):
  mnist.send(data=x, label=y)

mnist.close()