import tensorflow as tf
import tensorflow_datasets as tfds
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'so2sat-in'
OUTPUT_TOPIC = 'so2sat-out'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'
ITEMS_TO_PREDICT = 10

so2sat = tfds.load('so2sat', as_supervised=True, shuffle_files=True, 
                       split=[f"validation[:{ITEMS_TO_PREDICT}]"], data_dir='datasets/so2sat')

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""

for image, _ in so2sat[0]:
    producer.send(INPUT_TOPIC, image.numpy().tobytes())
    """Sends the value to predict to Kafka"""
producer.flush()
producer.close()

output_consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates an output consumer to receive the predictions"""

print('\n')

print('Output consumer: ')
for msg in output_consumer:
  print (msg.value.decode())