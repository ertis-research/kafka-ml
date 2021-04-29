import tensorflow as tf
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'minst-in'
OUTPUT_TOPIC = 'minst-out'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'
ITEMS_TO_PREDICT = 10

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
print("Datasize minst: ", x_test.shape)

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""
for i in range (0, ITEMS_TO_PREDICT):
  producer.send(INPUT_TOPIC, x_test[i].tobytes())
  """Sends the value to predict to Kafka"""
producer.flush()
producer.close()

output_consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates an output consumer to receive the predictions"""

print('\n')

print('Output consumer: ')
for msg in output_consumer:
  print (msg.value.decode())