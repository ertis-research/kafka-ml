

import sys
sys.path.append(sys.path[0] + "/../..")

from datasources.avro_inference import  AvroInference

import pandas as pd

from kafka import KafkaConsumer

from sklearn import preprocessing

import logging

INPUT_TOPIC = 'hcopd-in'
OUTPUT_TOPIC = 'hcopd-out'
BOOTSTRAP_SERVERS= '127.0.0.1:9094'
ITEMS_TO_PREDICT = 10

logging.basicConfig(level=logging.INFO)

copd_data = pd.read_csv('HCOPD_Dataset.csv')
"""Reads the HCOPD dataset"""

copd_data_columns = copd_data.columns

features = pd.DataFrame(preprocessing.scale(copd_data[copd_data_columns[copd_data_columns != 'Diagnosis']]))
"""All columns except Diagnosis"""

diagnosis = copd_data['Diagnosis']
"""Diagnosis column"""

hcopd = AvroInference(boostrap_servers='127.0.0.1:9094', topic=INPUT_TOPIC, 
                            data_scheme_filename='data_scheme.avsc')
"""Creates an Avro inference"""

for i in range (0, ITEMS_TO_PREDICT):
  data  = {"gender": features[0][i], "age": features[1][i], "smoking": features[2][i]}
  hcopd.send(data)
  """ Sends the value to predict to Kafka"""
logging.info("Data sent for prediction")
hcopd.close()

consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
"""Creates a consumer to receive the predictions"""

logging.info("Waiting for predictions")
for msg in consumer:
  print (msg.value.decode())