import tensorflow as tf
import tensorflow_datasets as tfds
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'eurosat-in'
OUTPUT_TOPIC = 'eurosat-out'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'
ITEMS_TO_PREDICT = 10

eurosat = tfds.load('eurosat', as_supervised=True, shuffle_files=True, 
                     split=[f"train[:{ITEMS_TO_PREDICT}]"], data_dir='datasets/eurosat')

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""

for image, _ in eurosat[0]:
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