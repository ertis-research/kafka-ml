import tensorflow as tf
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'vgg-in'
OUTPUT_TOPIC = 'vgg-out'
BOOTSTRAP_SERVERS= 'localhost:9094'
ITEMS_TO_PREDICT = 10

(x_train, y_train ), ( x_test, y_test ) = tf.keras.datasets.cifar10.load_data()
y_train = tf.keras.utils.to_categorical( y_train )
y_test = tf.keras.utils.to_categorical( y_test )


producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""

for i in range (0, ITEMS_TO_PREDICT):
  producer.send(INPUT_TOPIC, x_test[i].tobytes())
  """ Sends the value to predict to Kafka"""
producer.flush()
producer.close()

consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates a consumer to receive the predictions"""

for msg in consumer:
  print (msg.value.decode())

