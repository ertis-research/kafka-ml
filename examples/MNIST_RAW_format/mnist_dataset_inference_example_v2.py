import tensorflow as tf
import logging
from kafka import KafkaProducer, KafkaConsumer

logging.basicConfig(level=logging.INFO)

UPPER_TOPIC = 'minst-upper'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'

upper_consumer = KafkaConsumer(UPPER_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates an upper consumer to receive the predictions"""

print('\n')

print('Upper consumer: ')
for msg in upper_consumer:
  print (msg.value.decode())