import sys
sys.path.append(sys.path[0] + "/../..") 
"""To allow importing datasources"""

from datasources.raw_sink import  RawSink

import numpy as np
import pandas as pd

import logging
logging.basicConfig(level=logging.INFO)


df = pd.read_csv('MLGPARK_Dataset.csv')

target = "free_places"
features = df.drop(columns= "free_places").to_numpy()
labels=np.ravel(df[target])

print(features)


mlgpark = RawSink(boostrap_servers='localhost:9094', topic='automl', deployment_id=1,
        description='MLGPARK dataset', validation_rate=0.1, test_rate=0.1)

for (x, y) in zip(features, labels):
    mlgpark.send(data=x, label=y)

mlgpark.close()