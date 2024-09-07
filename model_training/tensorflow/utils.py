import tensorflow as tf
from tensorflow import keras
import urllib
import time
import logging
import json

from config import *
import numpy as np
import sys
import os
import subprocess as sp

PRE_MODEL_PATH = "pre_model.h5"
"""Path of the received pre-model"""

TRAINED_MODEL_PATH = "trained_model.h5"
"""Path of the trained model"""

CONFUSSION_MODEL_IMAGE = "confusion_matrix.png"
"""Path of the confussion matrix image"""

RETRIES = 10
"""Number of retries for requests"""

SLEEP_BETWEEN_REQUESTS = 5
"""Number of seconds between failed requests"""

"""CONSTANTS FOR TYPES OF TRAINING"""
NOT_DISTRIBUTED_NOT_INCREMENTAL = 1
NOT_DISTRIBUTED_INCREMENTAL = 2
DISTRIBUTED_NOT_INCREMENTAL = 3
DISTRIBUTED_INCREMENTAL = 4
FEDERATED_LEARNING = 5
FEDERATED_INCREMENTAL_LEARNING = 6
FEDERATED_DISTRIBUTED_LEARNING = 7
FEDERATED_DISTRIBUTED_INCREMENTAL_LEARNING = 8
BLOCKCHAIN_FEDERATED_LEARNING = 9


def download_model(model_url, filename, retries, sleep_time):
    """Downloads the model from the URL received and saves it in the filesystem
    Args:
        model_url(str): URL of the model
    """
    finished = False
    retry = 0
    while not finished and retry < retries:
        try:
            filedata = urllib.request.urlopen(model_url)
            datatowrite = filedata.read()
            with open(filename, "wb") as f:
                f.write(datatowrite)
            finished = True
            logging.info("Downloaded file model from server!")
        except Exception as e:
            retry += 1
            logging.error("Error downloading the model file [%s]", str(e))
            time.sleep(sleep_time)


def string_to_numpy_type(out_type):
    """Converts a string with the same name to a Numpy type.
    Acceptable types are half, float, double, int32, uint16, uint8,
                int16, int8, int64, string, bool.
    Args:
        out_type (str): Output type to convert
    Returns:
        Numpy DType: Numpy DType of the intput
    """
    if out_type == "half":
        return np.half
    elif out_type == "float":
        return np.float
    elif out_type == "float32":
        return np.float32
    elif out_type == "double":
        return np.double
    elif out_type == "int64":
        return np.int64
    elif out_type == "int32":
        return np.int32
    elif out_type == "int16":
        return np.int16
    elif out_type == "int8":
        return np.int8
    elif out_type == "uint16":
        return np.uint16
    elif out_type == "uint8":
        return np.uint8
    elif out_type == "string":
        return np.string
    elif out_type == "bool":
        return np.bool
    else:
        raise Exception("string_to_numpy_type: Unsupported type")


def load_model(model_path):
    """Returns the model saved previously in the filesystem.
    Args:
        model_path (str): path of the model
    Returns:
        Tensorflow model: tensorflow model loaded
    """
    model = keras.models.load_model(model_path)
    if DEBUG:
        model.summary()
        """Prints model architecture"""
    return model


def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed.
    Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)
    Returns:
        DType: raw data to tensorflow model loaded
    """
    # res = np.frombuffer(x, dtype=output_type)
    # output_reshape = np.insert(output_reshape, 0, 1, axis=0)
    # res = res.reshape(*output_reshape)
    res = tf.io.decode_raw(x, out_type=output_type)
    res = tf.reshape(res, output_reshape)
    return res


def decode_input(x, y, output_type_x, reshape_x, output_type_y, reshape_y):
    """Decodes the input data received from Kafka and reshapes it if needed.
    Args:
        x (bytes): train data
        output_type_x (:obj:DType): output type of the train data
        reshape_x (:obj:`list`): reshape the tensorflow train data (optional)
        y (bytes): label data
        out_type_y (:obj:DType): output type of the label data
        reshape_y (:obj:`list`): reshape the tensorflow label data (optional)
    Returns:
        tuple: tuple with the (train, label) data received
    """
    x = decode_raw(x, output_type_x, reshape_x)
    y = decode_raw(y, output_type_y, reshape_y)
    return (x, y)


def configure_logging():
    if DEBUG:
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.DEBUG,
            format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def select_gpu():
    ACCEPTABLE_AVAILABLE_MEMORY = 1024
    COMMAND = "nvidia-smi --query-gpu=memory.free --format=csv"

    try:
        _output_to_list = lambda x: x.decode("ascii").split("\n")[:-1]
        memory_free_info = _output_to_list(sp.check_output(COMMAND.split()))[1:]
        memory_free_values = [int(x.split()[0]) for i, x in enumerate(memory_free_info)]

        available_gpus = [
            i
            for i, x in enumerate(memory_free_values)
            if x > ACCEPTABLE_AVAILABLE_MEMORY
        ]
        print("Available GPUs:", available_gpus)
        if len(available_gpus) > 1:
            available_gpus = [memory_free_values.index(max(memory_free_values))]
            print("Using GPU:", available_gpus)

        os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, available_gpus))

        gpus = tf.config.experimental.list_physical_devices("GPU")
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    except Exception as e:
        print('"nvidia-smi" is probably not installed. GPUs are not masked.', e)


def load_distributed_environment_vars():
    """Loads the distributed environment information received from dockers
    optimizer, learning_rate, loss, metrics
    Returns:
        optimizer (str): optimizer
        learning_rate (decimal): learning rate
        loss (str): loss
        metrics (str): monitoring metrics
    """
    optimizer = os.environ.get("OPTIMIZER")
    learning_rate = eval(os.environ.get("LEARNING_RATE"))
    loss = os.environ.get("LOSS")
    metrics = os.environ.get("METRICS")

    return optimizer, learning_rate, loss, metrics


def load_incremental_environment_vars():
    """Loads the incremental environment information received from dockers
    stream_timeout, monitoring_metric, change, improvement
    Returns:
        stream_timeout (int): stream timeout to wait for new data
        monitoring_metric (str): metric to track for indefinite training
        change (str): direction in which monitoring metric improves
        improvement (decimal): how many the monitoring metric improves
    """
    stream_timeout = int(os.environ.get("STREAM_TIMEOUT"))
    monitoring_metric = os.environ.get("MONITORING_METRIC")
    change = os.environ.get("CHANGE")
    improvement = eval(os.environ.get("IMPROVEMENT"))

    return stream_timeout, monitoring_metric, change, improvement


def load_federated_environment_vars():
    """Loads the federated environment information received from dockers
    model_logger_topic, federated_string_id, agg_rounds, data_restriction, min_data, agg_strategy
    Returns:
        model_logger_topic (str): model control topic with the model information
        federated_string_id (str): federated string id
        agg_rounds (int): number of aggregation rounds
        data_restriction (str): data restriction
        min_data (int): minimum data to train
        agg_strategy (str): aggregation strategy
    """

    model_logger_topic = os.environ.get("MODEL_LOGGER_TOPIC")
    federated_string_id = os.environ.get("FEDERATED_STRING_ID")
    agg_rounds = int(os.environ.get("AGGREGATION_ROUNDS"))
    data_restriction = os.environ.get("DATA_RESTRICTION")
    min_data = int(os.environ.get("MIN_DATA"))
    agg_strategy = os.environ.get("AGG_STRATEGY")

    return (
        model_logger_topic,
        federated_string_id,
        agg_rounds,
        data_restriction,
        min_data,
        agg_strategy,
    )


def load_blockchain_federated_environment_vars():
    """Loads the blockchain federated environment information received from dockers
    eth_rpc_url, eth_token_address, eth_token_abi, eth_chain_id, eth_network_id, eth_wallet_address, eth_wallet_key, eth_blockscout_url
    Returns:
        eth_rpc_url (str): Ethereum RPC URL
        eth_token_address (str): Ethereum token address
        eth_token_abi (str): Ethereum token ABI
        eth_chain_id (int): Ethereum chain ID
        eth_network_id (int): Ethereum network ID
        eth_wallet_address (str): Ethereum wallet address
        eth_wallet_key (str): Ethereum wallet key
        eth_blockscout_url (str): Ethereum blockscout URL
    """

    eth_rpc_url = os.environ.get("ETH_RPC_URL")
    eth_token_address = os.environ.get("ETH_TOKEN_ADDRESS")
    eth_token_abi = json.loads(os.environ.get("ETH_TOKEN_ABI"))
    eth_chain_id = int(os.environ.get("ETH_CHAIN_ID"))
    eth_network_id = int(os.environ.get("ETH_NETWORK_ID"))
    eth_wallet_address = os.environ.get("ETH_WALLET_ADDRESS")
    eth_wallet_key = os.environ.get("ETH_WALLET_KEY")
    eth_blockscout_url = os.environ.get("ETH_BLOCKSCOUT_URL")

    return (
        eth_rpc_url,
        eth_token_address,
        eth_token_abi,
        eth_chain_id,
        eth_network_id,
        eth_wallet_address,
        eth_wallet_key,
        eth_blockscout_url,
    )
