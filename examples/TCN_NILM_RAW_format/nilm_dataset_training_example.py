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

# Downloadable at https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption
FILE_PATH = "examples/TCN_NILM_RAW_format/household_power_consumption.csv"
WINDOW_SIZE = 120


def create_sliding_windows(features, targets, window_size):
    X_windows, y_windows = [], []
    for i in range(len(features) - window_size):
        X_windows.append(features[i : i + window_size])
        y_windows.append(targets[i : i + window_size])
    return np.array(X_windows, dtype=np.float32), np.array(y_windows, dtype=np.float32)


def load_and_preprocess_data(file_path, window_size=120):
    """
    Load and preprocess the dataset from the given file path.
    Args:
        file_path (str): Path to the dataset file.
        window_size (int): Size of the sliding window for creating sequences.
    Returns:
        tuple: A tuple containing:
            - X (np.ndarray): Sliding windows of features.
            - y (np.ndarray): Sliding windows of targets.
    """
    data = pd.read_csv(
        file_path,
        sep=";",
        parse_dates={"DateTime": ["Date", "Time"]},
        infer_datetime_format=True,
        low_memory=False,
        na_values=["?"],
    )
    data = data.sort_values("DateTime").dropna()

    cols = [
        "Global_active_power",
        "Global_intensity",
        "Sub_metering_1",
        "Sub_metering_2",
        "Sub_metering_3",
    ]
    data[cols] = data[cols].astype("float32")

    # DEBUG: select a random sample of 1000 rows
    data = data.sample(n=1000, random_state=42).reset_index(drop=True)
    print(f"Sampled {len(data)} rows from the dataset.")

    features = data[["Global_active_power", "Global_intensity"]].values
    targets = data[["Sub_metering_1", "Sub_metering_2", "Sub_metering_3"]].values

    # scalers
    print("scalers saved as scaler_X_disagg.pkl / scaler_y_disagg.pkl")

    X, y = create_sliding_windows(features, targets, window_size)

    # shuffle X and y together
    index = np.arange(len(X))

    rng = np.random.default_rng(42)
    rng.shuffle(index)

    X = X[index]
    y = y[index]

    return X, y


X, y = load_and_preprocess_data(FILE_PATH, WINDOW_SIZE)

# Split the data into training, validation, and test sets
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42
)

nilm_sink = RawSink(
    boostrap_servers="localhost:9094",
    topic="automl",
    deployment_id=1,
    description="NILM dataset",
    validation_rate=0.15,
    test_rate=0.15,
)

for x, y in zip(X_train, y_train):
    nilm_sink.send(data=x, label=y)

for x, y in zip(X_test, y_test):
    nilm_sink.send(data=x, label=y)

nilm_sink.close()
