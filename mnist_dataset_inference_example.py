import tensorflow as tf
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'inference-input'
OUTPUT_TOPIC = 'inference-output'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
print("Datasize minst: ", x_test.shape)

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""

for x in x_test:
  producer.send(INPUT_TOPIC, x.tobytes())
  """ Sends the value to predict to Kafka"""
producer.flush()
producer.close()

consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates a consumer to receive the predictions"""

for msg in consumer:
  print (msg.value.decode())

