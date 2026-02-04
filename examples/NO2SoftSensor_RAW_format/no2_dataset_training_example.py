import sys

sys.path.append(sys.path[0] + "/../..")
"""To allow importing datasources"""

import tensorflow as tf
import numpy as np
import pandas as pd

import logging

from datasources.raw_sink import RawSink

from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO)


df = pd.read_csv("examples/NO2SoftSensor_RAW_format/DatasetFiltered.csv")

# parse float columns to float32
float_columns = ["ALK_MGL", "COND_USCM", "PH", "SS_MGL", "NO3_N_MGL"]
df[float_columns] = df[float_columns].astype(np.float32)

# Separate features and target variable
X = df.drop(columns=["NO3_N_MGL"]).to_numpy()
y = df["NO3_N_MGL"].values

# Split the data into training, validation, and test sets
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

nilm_sink = RawSink(
    boostrap_servers="localhost:9094",
    topic="automl",
    deployment_id=1,
    description="NO3 dataset",
    validation_rate=0.15,
    test_rate=0.15,
)

for x, y in zip(X_train, y_train):
    nilm_sink.send(data=x, label=y)

for x, y in zip(X_test, y_test):
    nilm_sink.send(data=x, label=y)

nilm_sink.close()
