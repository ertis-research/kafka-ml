import logging
from kafka import KafkaProducer, KafkaConsumer
import json
import urllib3
import datetime
import numpy as np
from kafka import KafkaProducer, KafkaConsumer

import logging
logging.basicConfig(level=logging.INFO)

INPUT_TOPIC = 'mlgpark-in'
OUTPUT_TOPIC = 'mlgpark-out'
BOOTSTRAP_SERVERS= 'localhost:9094'
url = 'https://datosabiertos.malaga.eu/api/3/action/datastore_search?resource_id=0dcf7abd-26b4-42c8-af19-4992f1ee60c6'  


producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)
"""Creates a producer to send the values to predict"""

### Get data from api
http = urllib3.PoolManager()
response = http.request('GET', url)
data = json.loads(response.data.decode('utf-8'))

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)

for x in data['result']['records']: 
	input_data = [int(x['poiID'])]

	if x['fechahora_ultima_actualizacion'] == 'None':
		date = datetime.datetime.now(datetime.timezone.utc).strftime("%d %m %Y %H %M").split(' ')
	else:
		date = datetime.datetime.strptime(x['fechahora_ultima_actualizacion'], '%Y-%m-%d %H:%M:%S UTC').strftime("%d %m %Y %H %M").split(' ')
		pass
	
	input_data += [np.int64(i) for i in date]  
	input_data = np.array(input_data)

	# Send data
	producer.send(INPUT_TOPIC, input_data.tobytes())


producer.flush()
producer.close()


output_consumer = KafkaConsumer(OUTPUT_TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, group_id="output_group")
print('\n')

print('Output consumer: ')
for msg in output_consumer:
  print (msg.value.decode())
output_consumer.close()   

