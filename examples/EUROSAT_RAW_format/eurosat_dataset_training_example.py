import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.raw_sink import  RawSink
import tensorflow as tf
import tensorflow_datasets as tfds
import logging

logging.basicConfig(level=logging.INFO)

eurosat = RawSink(boostrap_servers='localhost:9094', topic='automl', deployment_id=1,
        description='eurosat dataset', validation_rate=0.1, test_rate=0.1)

ds = tfds.load('eurosat', as_supervised=True, shuffle_files=True, data_dir='datasets/eurosat')
ds['train'] = ds['train'].shuffle(buffer_size=1000)

for image, label in ds['train']:
    eurosat.send(data=image.numpy(), label=label.numpy())

eurosat.close()