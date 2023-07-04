# Federated model training

This module contains the federated training task that will be executed when a TensorFlow training Job is launched in Kafka-ML federated through Kubernetes. Once deployed, this task waits until a message with the model architecture is received and is valid configured. Once received the model and the corresponding data stream, the downloaded TensorFlow model from Kafka-ML Cloud will be trained, and the trained model and training and optionally validation results will be sent again to the backend.

A brief introduction of its files:
- File `federated_training.py` main file of this module that will be executed when executed the training Job.
- File `KafkaModelEngine.py` class contains all the necesary functions to read and load Tensorflow models from Apache Kafka in cloud.
- File `FederatedKafkaMLAggregationSink.py` class contains all the necesary functions to send the trained model and metrics to Apache Kafka in cloud.
- File `federated_mainTraining.py` and `federated_singleClassicTraining.py` contains the functions for each kind of federated training.
- File `decoders.py` decoders (RAW, Avro, JSON) used to decode data streams.
- File `config.py` to configure debug.
- File `utils.py` common functions used by other files.

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

Once installed, you have to set each one of the environment vars below to execute the training task. For instance, you can run `export BOOTSTRAP_SERVERS=localhost:9094` to export the `BOOTSTRAP_SERVERS` var with the value `localhost:9094`. Once configured all the vars, execute `python training.py` to execute the training task.

## Environments vars received

- **KML_CLOUD_BOOTSTRAP_SERVERS**: Kafka bootstrap servers to connect to Kafka-ML Cloud.
- **DATA_BOOTSTRAP_SERVERS**:  Kafka bootstrap servers to connect to the data stream in federated Kafka.
- **DATA_TOPIC**: Kafka topic where the data stream is published (at federated Kafka).
- **INPUT_FORMAT**: Format of the data stream (RAW, AVRO, JSON).
- **INPUT_CONFIG**: Data type and structure of the data.
- **VALIDATION_RATE**: Percentage of data used for validation.
- **TOTAL_MSG**: Total number of messages to be received.
- **FEDERATED_MODEL_ID**: ID of the model to be trained.