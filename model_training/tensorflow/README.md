# Model training

This module contains the training task that will be executed when a TensorFlow training Job is launched in Kafka-ML through Kubernetes. Once deployed, this task waits until a received control message contains the `deployment_id` configured. Once received the control message and the corresponding data stream, the downloaded TensorFlow model from the Back-end will be trained, and the trained model and training and optionally validation results will be sent again to the Back-end.

A brief introduction of its files:
- File `training.py` main file of this module that will be executed when executed the training Job.
- File `decoders.py` decoders (RAW, Avro) used to decode data streams.
- File `config.py` to configure debug.
- File `utils.py` common functions used by other files.

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

Once installed, you have to set each one of the environment vars below to execute the training task. For instance, you can run `export BOOTSTRAP_SERVERS=localhost:9094` to export the `BOOTSTRAP_SERVERS` var with the value `localhost:9094`. Once configured all the vars, execute `python training.py` to execute the training task.

## Environments vars received

- **BOOTSTRAP_SERVERS**: list of brokers for the connection to Apache Kafka
- **RESULT_URL**: URL for downloading the untrained model from the Back-end (GET request). This URL is the same for updating the training results (POST request).
- **RESULT_ID**: Result ID of the model
- **CONTROL_TOPIC**: name of the Kafka control topic used in Kafka-ML
- **DEPLOYMENT_ID**: deployment ID of the configuration to match with the control messages received
- **BATCH**: Batch size used for training and configured in the Front-end
- **KWARGS_FIT**: JSON with the arguments used for training and configured in the Front-end
- **KWARGS_VAL**: JSON with the arguments used for validation and configured in the Front-end
