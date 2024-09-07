__author__ = "Antonio J. Chaves"

from kafka import KafkaConsumer

import os
import logging
import json
import traceback

from config import *
from utils import *
from FederatedKafkaMLAggregationSink import FederatedKafkaMLAggregationSink

RETRIES = 10
"""Number of retries for requests"""

SLEEP_BETWEEN_REQUESTS = 5
"""Number of seconds between failed requests"""


def blockchainFederatedTraining(training):
    try:
        logging.info("Starting federated training with blockchain")
        sink = FederatedKafkaMLAggregationSink(
            bootstrap_servers=training.kml_cloud_bootstrap_server,
            topic=training.aggregation_data_topic,
            control_topic=training.aggregation_control_topic,
            federated_id=training.group_id,
        )

        """Read model from Kafka"""
        last_round = None

        while training.isTrainingActive():
            n_round = training.get_current_round()
            try:
                if last_round is None or last_round != n_round:
                    last_round = n_round
                    logging.info("Current round: %s", n_round)

                    # get global model given the round
                    model_message = training.get_global_model(n_round)
                    logging.info("Model dir received, trying to load")

                    logging.info("Received message: %s", str(model_message))

                    model = training.load_model(model_message)
                    logging.info("Model received and loaded, trying to start training")
                    model.summary()

                    training_settings = model_message["training_settings"]

                    if training.kafka_dataset is None:
                        training.get_data(training_settings)

                    logging.info(
                        "Starting training with settings: {}".format(training_settings)
                    )
                    model_trained = training.train(model, training_settings)

                    epoch_training_metrics, epoch_validation_metrics = training.save_metrics(model_trained)
                    metrics = {
                        "training": epoch_training_metrics,
                        "validation": epoch_validation_metrics,
                    }

                    model_control_msg = sink.send_model_and_metrics(
                        model, metrics, model_message["version"], training.total_msg
                    )

                    tx_hash = training.send_updated_model(
                        model_control_msg, metrics, training.total_msg
                    )
                    logging.info(
                        "Update submitted to blockchain with hash: %s", tx_hash
                    )
            except Exception as e:
                traceback.print_exc()
                logging.error(
                    "Error with the received data [%s]. Waiting for new a new prediction.",
                    str(e),
                )

        sink.close()
        logging.info(
            "Model trained and sent the final weights to the aggregation topic"
        )

    except Exception as e:
        traceback.print_exc()
        logging.error("Error in main [%s]. Service will be restarted.", str(e))
