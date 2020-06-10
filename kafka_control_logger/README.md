# Model inference

This module contains the Kafka control logger that consumes control Kafka-ML messages to send them to the Back-end. That's all. These messages will be used in the Back-end to reuse the data streams and send them to other deployed training tasks.

A brief introduction of its files:
- File `logger.py` main file of this module.

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

Once installed, you have to set each one of the environment vars below to execute this task. For instance, you can run `export CONTROL_TOPIC=control` to export the `CONTROL_TOPIC` var with the value `control`. Once configured all the vars, execute `python logger.py` to execute this task.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka.
- **BACKEND**: hostname and port of the Back-end (e.g., localhost:8000).
- **CONTROL_TOPIC**: name of the Kafka control topic.