# Federated Kafka Model Control Logger

This module contains the Federated Kafka model control logger that consumes model control Kafka-ML messages to send them to the federated backend. That's all. These messages will be used in the federated backend to check if the models are suitable to be deployed in the federated learning environment given the received data streams.

A brief introduction of its files:
- File `federated_model_control_logger.py` main file of this module.

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

Once installed, you have to set each one of the environment vars below to execute this task. For instance, you can run `export CONTROL_TOPIC=control` to export the `CONTROL_TOPIC` var with the value `control`. Once configured all the vars, execute `python federated_model_control_logger.py` to execute this task.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka.
- **BACKEND**: hostname and port of the Back-end (e.g., localhost:8000).
- **CONTROL_TOPIC**: name of the Kafka control topic.