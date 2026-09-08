from utils import *
import json
import time

import tensorflow_io.kafka as kafka_io
from kafka import KafkaConsumer
from kafka.structs import OffsetAndMetadata
from confluent_kafka.admin import AdminClient, NewTopic

from KafkaModelEngine import KafkaModelEngine

from decoders import *

class MainTraining(object):
    """Main class for training
    
    Attributes:
        kml_cloud_bootstrap_server (str): Kafka bootstrap server for the KML Cloud
        data_bootstrap_server (str): Kafka bootstrap server for data
        federated_model_id (str): Federated model ID
        input_data_topic (str): Input data topic
        input_format (str): Input data format
        input_config (dict): Input data configuration
        validation_rate (float): Validation rate
        total_msg (int): Total number of messages
    """

    def __init__(self):
        """Loads the environment information"""

        self.kml_cloud_bootstrap_server = os.environ.get('KML_CLOUD_BOOTSTRAP_SERVERS')
        self.data_bootstrap_server = os.environ.get('DATA_BOOTSTRAP_SERVERS')

        self.federated_model_id = os.environ.get('FEDERATED_MODEL_ID')
        self.federated_client_id = os.environ.get('FEDERATED_CLIENT_ID')

        self.input_data_topic = os.environ.get('DATA_TOPIC')
        self.unsupervised_data_topic = os.environ.get('UNSUPERVISED_TOPIC')
        self.input_format = os.environ.get('INPUT_FORMAT')
        self.input_config = json.loads(os.environ.get('INPUT_CONFIG'))

        self.validation_rate = float(os.environ.get('VALIDATION_RATE'))
        self.total_msg = -1 if os.environ.get('TOTAL_MSG') == 'None' else int(os.environ.get('TOTAL_MSG'))

        logging.info("Received main environment information (KML_CLOUD_BOOTSTRAP_SERVERS, DATA_BOOTSTRAP_SERVERS, FEDERATED_MODEL_ID, DATA_TOPIC, INPUT_FORMAT, INPUT_CONFIG, VALIDATION_RATE, TOTAL_MSG) ([%s], [%s], [%s], [%s], [%s], [%s], [%f], [%d])",
                        self.kml_cloud_bootstrap_server, self.data_bootstrap_server, self.federated_model_id, self.input_data_topic, self.input_format, self.input_config, self.validation_rate, self.total_msg)

        # Syntetic data
        if self.total_msg != -1:
            self.training_size = int((1-(float(self.validation_rate)))*(int(self.total_msg)))
        self.kafka_dataset = None
        self._supervised_kafka_consumer = None
        if self.unsupervised_data_topic is not None:
            self.unsupervised_kafka_dataset = None

        self.model_trained = None

        # Create Kafka-related variables
        self.model_control_topic = f'FED-{self.federated_model_id}-model_control_topic'
        self.model_data_topic = f'FED-{self.federated_model_id}-model_data_topic'
        self.aggregation_control_topic = f'FED-{self.federated_model_id}-agg_control_topic'
        self.aggregation_data_topic = f'FED-{self.federated_model_id}-agg_data_topic-{self.federated_client_id}'
        self.group_id = f'FED-MODEL-{self.federated_model_id}-CLIENT-{self.federated_client_id}'

        # Set up the admin client
        admin_client = AdminClient({'bootstrap.servers': self.kml_cloud_bootstrap_server})

        topics_to_create = []
        topics_to_create.append(NewTopic(self.aggregation_data_topic, 1, config={'max.message.bytes': '10000000'}))   # 10 MB

        admin_client.create_topics(topics_to_create)

        # Wait for the topic to be created
        topic_created = False
        while not topic_created:
            topic_metadata = admin_client.list_topics(timeout=-1)
            if self.aggregation_data_topic in topic_metadata.topics: 
                topic_created = True

    def get_kafka_dataset(self, training_settings):
        logging.info("Fetching labeled dataset from Kafka Topic [%s], with bootstrap server [%s]", self.input_data_topic, self.data_bootstrap_server)  

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        self.kafka_dataset = kafka_io.KafkaDataset(self.input_data_topic, servers=self.data_bootstrap_server, group=self.group_id, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))
        self.train_dataset = self.kafka_dataset.take(self.training_size).batch(training_settings['batch'])
        self.validation_dataset = self.kafka_dataset.skip(self.training_size).batch(training_settings['batch'])

        logging.info("Dataset fetched successfully")
    
    def get_unsupervised_kafka_dataset(self, training_settings):
        logging.info("Fetching unlabeled dataset from Kafka Topic [%s], with bootstrap server [%s]", self.unsupervised_data_topic, self.data_bootstrap_server)  

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        self.unsupervised_kafka_dataset = kafka_io.KafkaDataset(self.unsupervised_data_topic, servers=self.data_bootstrap_server, group=self.group_id, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y)).batch(training_settings['batch'])

        logging.info("Unlabeled dataset fetched successfully")

    def get_online_kafka_dataset(self, training_settings):
        """Creates the persistent labeled Kafka consumer used by incremental training."""

        if self._supervised_kafka_consumer is None:
            logging.info("Creating persistent labeled Kafka consumer for topic [%s], with bootstrap server [%s]", self.input_data_topic, self.data_bootstrap_server)

            self._supervised_kafka_consumer = KafkaConsumer(self.input_data_topic, bootstrap_servers=self.data_bootstrap_server, group_id=self.group_id + "-2", auto_offset_reset="earliest", enable_auto_commit=False, max_poll_records=10000, max_poll_interval_ms=3600000)

            logging.info("Persistent labeled Kafka consumer created successfully with group [%s]", self.group_id + "-2")
        else:
            logging.info("Reusing persistent labeled Kafka consumer with group [%s]", self.group_id + "-2")

        self.kafka_dataset = self._supervised_kafka_consumer

    def close_online_kafka_consumer(self):
        """Closes the persistent labeled Kafka consumer."""

        consumer = self._supervised_kafka_consumer

        if consumer is None:
            return

        logging.info("Closing persistent labeled Kafka consumer")

        consumer.close(autocommit=False)
        self._supervised_kafka_consumer = None
        self.kafka_dataset = None

        logging.info("Persistent labeled Kafka consumer closed")

    def get_online_unsupervised_kafka_dataset(self, training_settings):
        """Fetches the unlabeled portion available for the current incremental round."""

        first_incremental_round = not hasattr(self, "model_trained") or self.model_trained is None

        if not hasattr(self, "_unsupervised_kafka_consumer") or self._unsupervised_kafka_consumer is None:
            logging.info("Creating persistent unlabeled Kafka consumer for topic [%s], with bootstrap server [%s]", self.unsupervised_data_topic, self.data_bootstrap_server)

            self._unsupervised_kafka_consumer = KafkaConsumer(self.unsupervised_data_topic, bootstrap_servers=self.data_bootstrap_server, group_id=self.group_id + "-unsupervised", auto_offset_reset="earliest", enable_auto_commit=False, max_poll_records=10000, max_poll_interval_ms=3600000)

            logging.info("Persistent unlabeled Kafka consumer created successfully")

        message_poll_timeout = 10000
        stream_timeout = training_settings["stream_timeout"]

        if stream_timeout == -1:
            close_on_inactivity = False
        elif stream_timeout >= 0:
            stream_timeout = max(stream_timeout, message_poll_timeout)
            close_on_inactivity = True
        else:
            raise ValueError("Invalid stream_timeout value: {}. Set it to -1 to block indefinitely.".format(stream_timeout))

        raw_messages = []
        raw_keys = []

        first_round_deadline = None
        inactivity_deadline = None

        if first_incremental_round and close_on_inactivity:
            first_round_deadline = time.monotonic() + (stream_timeout / 1000.0)
            logging.info("First semi-supervised incremental round: waiting up to %d ms for optional unlabeled data", stream_timeout)
        elif first_incremental_round:
            logging.info("First semi-supervised incremental round: waiting for unlabeled data")
        else:
            logging.info("Semi-supervised incremental round after labeled initialization: waiting until at least one unlabeled message is received")

        while True:
            if raw_messages:
                if close_on_inactivity:
                    remaining_ms = int((inactivity_deadline - time.monotonic()) * 1000)

                    if remaining_ms <= 0:
                        break

                    current_poll_timeout = min(message_poll_timeout, remaining_ms)
                else:
                    current_poll_timeout = message_poll_timeout
            elif first_incremental_round and close_on_inactivity:
                remaining_ms = int((first_round_deadline - time.monotonic()) * 1000)

                if remaining_ms <= 0:
                    break

                current_poll_timeout = min(message_poll_timeout, remaining_ms)
            else:
                current_poll_timeout = message_poll_timeout

            polled_records = self._unsupervised_kafka_consumer.poll(timeout_ms=current_poll_timeout, max_records=10000)

            if not polled_records:
                if raw_messages:
                    logging.info("No additional unlabeled Kafka data received during the last %d ms", current_poll_timeout)
                else:
                    logging.info("No initial unlabeled Kafka data received during the last %d ms", current_poll_timeout)

                continue

            received_messages = 0

            for partition_records in polled_records.values():
                for record in partition_records:
                    raw_messages.append(record.value)
                    raw_keys.append(record.key if record.key is not None else b"")
                    received_messages += 1

            logging.info("Received %d unlabeled Kafka messages; current round total: %d", received_messages, len(raw_messages))

            if close_on_inactivity:
                inactivity_deadline = time.monotonic() + (stream_timeout / 1000.0)

        if len(raw_messages) == 0:
            if first_incremental_round:
                self.unsupervised_kafka_dataset = []
                logging.info("No unlabeled data received during the first incremental window; continuing with labeled training only")
                return

            raise RuntimeError("No unlabeled Kafka messages were received after the labeled initialization round.")

        self._unsupervised_kafka_consumer.commit()

        round_dataset = tf.data.Dataset.from_tensor_slices((raw_messages, raw_keys))
        self.unsupervised_kafka_dataset = [round_dataset]

        logging.info("Unlabeled incremental dataset fetched successfully: %d messages in one federated-round dataset", len(raw_messages))

    def close_online_unsupervised_kafka_consumer(self):
        """Closes the persistent unlabeled Kafka consumer."""

        consumer = getattr(self, "_unsupervised_kafka_consumer", None)

        if consumer is None:
            return

        logging.info("Closing persistent unlabeled Kafka consumer")

        consumer.close(autocommit=False)
        self._unsupervised_kafka_consumer = None

        logging.info("Persistent unlabeled Kafka consumer closed")
    
    def split_online_dataset(self, kafka_dataset):
        """Splits the online dataset for training and validation"""

        training_size = int((1-self.validation_rate)*len(kafka_dataset))
        validation_size = int(self.validation_rate*len(kafka_dataset))
        logging.info("Training batch size %d and validation batch size %d", training_size, validation_size)

        train_dataset = kafka_dataset.take(training_size)
        """Splits dataset for training"""

        if validation_size > 0:
            validation_dataset = kafka_dataset.skip(training_size)
        else:
            """If no validation is greater than 0, then split the dataset for training"""
            validation_dataset = None

        splits = {
            'train_dataset': train_dataset,
            'validation_dataset': validation_dataset
        }

        return splits
    
    def load_model(self, message):
        model_reader = KafkaModelEngine(self.kml_cloud_bootstrap_server, self.group_id)
        model = model_reader.getModel(message)

        return model
    
    @staticmethod
    def _canonical_name(value):
        """Returns a canonical name for a Keras loss or activation"""

        if value is None:
            return ""

        if isinstance(value, str):
            name = value
        elif getattr(value, "name", None):
            name = value.name
        elif getattr(value, "__name__", None):
            name = value.__name__
        else:
            name = value.__class__.__name__

        return str(name).lower().replace("_", "").replace("-", "").replace(" ", "")

    def _detect_semi_supervised_task(self, model):
        """Automatically detects classification or regression"""

        if hasattr(self, "_semi_supervised_task"):
            return self._semi_supervised_task

        classification_losses = {
            "binarycrossentropy",
            "categoricalcrossentropy",
            "sparsecategoricalcrossentropy",
            "binaryfocalcrossentropy",
            "categoricalfocalcrossentropy",
        }

        regression_losses = {
            "mse",
            "meansquarederror",
            "mae",
            "meanabsoluteerror",
            "mape",
            "meanabsolutepercentageerror",
            "msle",
            "meansquaredlogarithmicerror",
            "huber",
            "huberloss",
            "logcosh",
            "poisson",
        }

        model_loss = model.loss

        if isinstance(model_loss, dict):
            configured_losses = list(model_loss.values())
        elif isinstance(model_loss, (list, tuple)):
            configured_losses = list(model_loss)
        else:
            configured_losses = [model_loss]

        loss_names = {self._canonical_name(loss) for loss in configured_losses if loss is not None}

        classification_detected = bool(loss_names.intersection(classification_losses))
        regression_detected = bool(loss_names.intersection(regression_losses))

        if classification_detected and regression_detected:
            raise ValueError("Semi-supervised task cannot be detected because the model combines classification and regression losses.")

        if classification_detected:
            task = "classification"
        elif regression_detected:
            task = "regression"
        else:
            # Fallback: inspect the activation of the final output layer
            final_layer = model.layers[-1]

            # Distributed models may contain a nested Cloud submodel
            while (hasattr(final_layer, "layers") and final_layer.layers):
                nested_layer = final_layer.layers[-1]

                if nested_layer is final_layer:
                    break

                final_layer = nested_layer

            activation_name = self._canonical_name(getattr(final_layer, "activation", None))

            if activation_name in {"softmax", "sigmoid"}:
                task = "classification"
            elif activation_name == "linear":
                task = "regression"
            else:
                raise ValueError("Kafka-ML could not automatically determine whether the semi-supervised model performs classification or regression. Use a supported loss function.")

        self._semi_supervised_task = task

        logging.info("Semi-supervised task automatically detected as [%s]. Configured losses: %s", task, sorted(loss_names))

        return task

    def _generate_pseudo_labels(self, model, predictions):
        """Generates confidence scores and pseudo-labels"""

        task = self._detect_semi_supervised_task(model)

        distributed_predictions = isinstance(predictions, (list, tuple))

        prediction_outputs = (list(predictions) if distributed_predictions else [predictions])

        final_predictions = np.asarray(prediction_outputs[-1])

        if final_predictions.ndim == 1:
            final_predictions = np.expand_dims(final_predictions, axis=1)

        if task == "classification":
            model_loss = model.loss

            if isinstance(model_loss, dict):
                configured_losses = list(model_loss.values())
            elif isinstance(model_loss, (list, tuple)):
                configured_losses = list(model_loss)
            else:
                configured_losses = [model_loss]

            loss_names = {self._canonical_name(loss) for loss in configured_losses if loss is not None}

            if final_predictions.shape[1] == 1:
                # Binary classification with a sigmoid output
                positive_probability = final_predictions[:, 0]

                confidence_scores = np.maximum(positive_probability, 1.0 - positive_probability)

                pseudo_labels = (positive_probability >= 0.5).astype(np.float32)

                pseudo_labels = np.expand_dims(pseudo_labels, axis=1)
            else:
                # Multiclass classification with a Softmax output
                confidence_scores = np.max(final_predictions, axis=1)

                class_indices = np.argmax(final_predictions, axis=1)

                if loss_names.intersection({"categoricalcrossentropy", "categoricalfocalcrossentropy"}):
                    pseudo_labels = np.eye(final_predictions.shape[1], dtype=np.float32)[class_indices]
                elif loss_names.intersection({"sparsecategoricalcrossentropy"}):
                    pseudo_labels = np.expand_dims(class_indices, axis=1)
                else:
                    raise ValueError("Automatic semi-supervised multiclass classification requires categorical_crossentropy or sparse_categorical_crossentropy.")

            return confidence_scores, pseudo_labels

        # Regression requires several prediction outputs so that confidence can be estimated from their agreement
        if len(prediction_outputs) < 2:
            raise ValueError("Automatic semi-supervised regression currently requires a distributed model with at least two prediction outputs.")

        pseudo_labels = final_predictions.astype(np.float32)

        epsilon = np.finfo(np.float32).eps
        disagreements = []

        for intermediate_output in prediction_outputs[:-1]:
            intermediate_predictions = np.asarray(intermediate_output)

            if intermediate_predictions.ndim == 1:
                intermediate_predictions = np.expand_dims(intermediate_predictions, axis=1)

            if intermediate_predictions.shape != final_predictions.shape:
                raise ValueError("All distributed regression outputs must have the same shape to calculate pseudo-label confidence.")

            relative_disagreement = (np.abs(intermediate_predictions - final_predictions) / (np.abs(intermediate_predictions) + np.abs(final_predictions) + epsilon))

            disagreements.append(np.mean(relative_disagreement, axis=1))

        maximum_disagreement = np.max(np.stack(disagreements, axis=1), axis=1)

        confidence_scores = 1.0 - np.clip(maximum_disagreement, 0.0, 1.0)

        return confidence_scores, pseudo_labels

    @staticmethod
    def _get_array_fit_kwargs(training_settings):
        """Returns fit arguments for NumPy inputs using the batch size selected in the deployment form."""

        fit_kwargs = dict(training_settings['kwargs_fit'])
        fit_kwargs['batch_size'] = training_settings['batch']

        return fit_kwargs

    def train_classic_model(self, model, training_settings):
        """Trains classic model"""

        start = time.time()
        model_trained = model.fit(self.train_dataset, validation_data=self.validation_dataset, **training_settings['kwargs_fit'], **training_settings['kwargs_val'])
        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))
        
        return model_trained
    
    def train_classic_semi_supervised_model(self, model, training_settings):
        """Trains semi-supervised model"""

        logging.info("Using training batch size [%d] from deployment settings", training_settings['batch'])

        x_train = np.concatenate([x for x, y in self.train_dataset], axis=0)
        y_train = np.concatenate([y for x, y in self.train_dataset], axis=0)

        x_val = np.concatenate([x for x, y in self.validation_dataset], axis=0)
        y_val = np.concatenate([y for x, y in self.validation_dataset], axis=0)

        logging.info("Training model with labeled data")

        start = time.time()

        if 'N' not in training_settings:
            model_trained = model.fit(x=x_train, y=y_train, validation_data=(x_val, y_val), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
        else:
            y_training = []
            y_validation = []
            for i in range(training_settings['N']):
                y_training.append(y_train)
                y_validation.append(y_val)
            model_trained = model.fit(x=x_train, y=y_training, validation_data=(x_val, y_validation), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])

        x_unlabeled = np.concatenate([x for x, y in self.unsupervised_kafka_dataset], axis=0)

        for round in range(training_settings['unsupervised_rounds']):
            if len(x_unlabeled) > 0:
                predictions = model.predict(x_unlabeled)

                (confidence_scores, pseudo_labels) = self._generate_pseudo_labels(model, predictions)

                high_confidence_indices = confidence_scores >= training_settings['confidence']
                high_confidence_pseudo_labels = pseudo_labels[high_confidence_indices]
                high_confidence_unlabeled_data = x_unlabeled[high_confidence_indices]

                if len(high_confidence_pseudo_labels) == 0:
                    logging.info("No high-confidence pseudo-labels found. Stopping.")
                    break
                else:
                    logging.info("Round %d: Found %d high-confidence pseudo-labels", round, len(high_confidence_pseudo_labels))

                x_combined = np.concatenate([x_train, high_confidence_unlabeled_data])
                y_combined = np.concatenate([y_train, high_confidence_pseudo_labels])

                logging.info("Training model with labeled and pseudo-labeled data")

                if 'N' not in training_settings:
                    unsupervised_model_trained = model.fit(x_combined, y_combined, validation_data=(x_val, y_val), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
                else:
                    y_training = []
                    for i in range(training_settings['N']):
                        y_training.append(y_combined)
                    unsupervised_model_trained = model.fit(x_combined, y_training, validation_data=(x_val, y_validation), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])

                x_train = x_combined
                y_train = y_combined

                x_unlabeled = np.delete(x_unlabeled, high_confidence_indices, axis=0)

                for key in model_trained.history.keys():
                    model_trained.history[key].extend(unsupervised_model_trained.history[key])
            else:
                logging.info("No more unlabeled data. Stopping.")
                break
        
        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))

        return model_trained
    
    def train_incremental_model(self, model, training_settings):
        """Trains one supervised incremental federated round."""

        consumer = self._supervised_kafka_consumer

        if consumer is None:
            raise RuntimeError("The persistent labeled Kafka consumer has not been created.")

        stream_timeout = training_settings["stream_timeout"]

        if stream_timeout < 0:
            raise ValueError("Supervised incremental federated training requires a non-negative stream_timeout to delimit each round.")

        message_poll_timeout = 1000
        stream_timeout = max(stream_timeout, message_poll_timeout)

        raw_messages = []
        raw_keys = []
        first_offsets = {}
        next_offsets = {}
        poll_count = 0
        inactivity_deadline = None

        logging.info("Waiting for the first labeled Kafka message for the current federated round")

        while True:
            if raw_messages:
                remaining_ms = int((inactivity_deadline - time.monotonic()) * 1000)

                if remaining_ms <= 0:
                    break

                current_poll_timeout = min(message_poll_timeout, remaining_ms)
            else:
                current_poll_timeout = message_poll_timeout

            polled_records = consumer.poll(timeout_ms=current_poll_timeout, max_records=10000)

            if not polled_records:
                continue

            received_messages = 0

            for topic_partition, partition_records in polled_records.items():
                if not partition_records:
                    continue

                if topic_partition not in first_offsets:
                    first_offsets[topic_partition] = partition_records[0].offset

                for record in partition_records:
                    raw_messages.append(record.value)
                    raw_keys.append(record.key if record.key is not None else b"")
                    next_offsets[topic_partition] = record.offset + 1
                    received_messages += 1

            if received_messages > 0:
                poll_count += 1
                inactivity_deadline = time.monotonic() + (stream_timeout / 1000.0)
                logging.info("Received %d labeled Kafka messages; current round total: %d", received_messages, len(raw_messages))

        round_message_count = len(raw_messages)

        if round_message_count == 0:
            raise RuntimeError("The supervised incremental Kafka window finished without messages.")

        logging.info("Labeled incremental Kafka window closed after %d ms of inactivity: %d messages from %d polls", stream_timeout, round_message_count, poll_count)

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)
        start = time.time()

        try:
            round_dataset = tf.data.Dataset.from_tensor_slices((raw_messages, raw_keys))
            decoded_dataset = round_dataset.map(lambda x, y: decoder.decode(x, y)).batch(training_settings['batch'])

            x_parts = []
            y_parts = []

            for x_batch, y_batch in decoded_dataset:
                x_parts.append(np.asarray(x_batch))
                y_parts.append(np.asarray(y_batch))

            if not x_parts or not y_parts:
                raise RuntimeError("The supervised incremental Kafka messages could not be decoded.")

            x_round = np.concatenate(x_parts, axis=0)
            y_round = np.concatenate(y_parts, axis=0)

            if len(x_round) != round_message_count or len(y_round) != round_message_count:
                raise RuntimeError("The decoded supervised round size does not match the Kafka message count.")

            training_size = int((1.0 - self.validation_rate) * round_message_count)
            validation_size = round_message_count - training_size

            if training_size <= 0:
                raise RuntimeError("The supervised incremental round contains no training samples after splitting.")

            x_train = x_round[:training_size]
            y_train = y_round[:training_size]

            if validation_size > 0:
                x_val = x_round[training_size:]
                y_val = y_round[training_size:]
                validation_data = (x_val, y_val)
            else:
                x_val = None
                y_val = None
                validation_data = None

            logging.info("Labeled incremental dataset fetched successfully: %d messages", round_message_count)
            logging.info("Training samples: %d; validation samples: %d", training_size, validation_size)

            if 'N' not in training_settings:
                model_trained = model.fit(x=x_train, y=y_train, validation_data=validation_data, **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
            else:
                y_training = []
                y_validation = []

                for i in range(training_settings['N']):
                    y_training.append(y_train)

                    if y_val is not None:
                        y_validation.append(y_val)

                distributed_validation_data = (x_val, y_validation) if x_val is not None else None
                model_trained = model.fit(x=x_train, y=y_training, validation_data=distributed_validation_data, **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])

        except Exception:
            assigned_partitions = consumer.assignment()

            for topic_partition, first_offset in first_offsets.items():
                if topic_partition in assigned_partitions:
                    consumer.seek(topic_partition, first_offset)

            logging.exception("Supervised incremental training failed. Kafka positions were restored to the beginning of the current round.")
            raise

        commit_offsets = {topic_partition: OffsetAndMetadata(next_offset, None) for topic_partition, next_offset in next_offsets.items()}
        commit_error = None

        for attempt in range(1, 4):
            try:
                consumer.commit(offsets=commit_offsets)

                for topic_partition, expected_offset in next_offsets.items():
                    committed_offset = consumer.committed(topic_partition)

                    if committed_offset != expected_offset:
                        raise RuntimeError("Unexpected committed offset for {}[{}]: expected {}, received {}.".format(topic_partition.topic, topic_partition.partition, expected_offset, committed_offset))

                commit_error = None
                break

            except Exception as error:
                commit_error = error
                logging.warning("Could not commit the supervised incremental Kafka round on attempt %d/3: %s", attempt, str(error))

                if attempt < 3:
                    time.sleep(1)

        if commit_error is not None:
            raise RuntimeError("The supervised incremental Kafka round was trained but its offsets could not be committed.") from commit_error

        committed_summary = {"{}[{}]".format(topic_partition.topic, topic_partition.partition): next_offset for topic_partition, next_offset in next_offsets.items()}

        end = time.time()

        logging.info("Model trained successfully. Elapsed time: [%f]", end - start)
        logging.info("Loss: %s", str(model_trained.history['loss'][-1]))
        logging.info("Committed labeled incremental Kafka round: %d messages; offsets=%s", round_message_count, committed_summary)

        return model_trained

    def train_incremental_semi_supervised_model(self, model, training_settings):
        """Trains incremental semi-supervised model."""

        logging.info("Using training batch size [%d] from deployment settings", training_settings['batch'])

        first_incremental_round = not hasattr(self, "model_trained") or self.model_trained is None
        start = time.time()

        if first_incremental_round:
            logging.info("Loading labeled data for the initial incremental round")

            train_batches = list(self.train_dataset)
            validation_batches = list(self.validation_dataset)

            x_train = np.concatenate([x for x, y in train_batches], axis=0)
            y_train = np.concatenate([y for x, y in train_batches], axis=0)
            x_val = np.concatenate([x for x, y in validation_batches], axis=0)
            y_val = np.concatenate([y for x, y in validation_batches], axis=0)

            self._validation_data_cache = (x_val, y_val)

            logging.info("Initial labeled data loaded: train=%d, validation=%d", len(x_train), len(x_val))
            logging.info("Training model with labeled data")

            if 'N' not in training_settings:
                self.model_trained = model.fit(x=x_train, y=y_train, validation_data=(x_val, y_val), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
            else:
                y_training = []
                y_validation = []

                for i in range(training_settings['N']):
                    y_training.append(y_train)
                    y_validation.append(y_val)

                self.model_trained = model.fit(x=x_train, y=y_training, validation_data=(x_val, y_validation), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
        else:
            if not hasattr(self, "_validation_data_cache"):
                raise RuntimeError("Validation data are not available after the labeled initialization round.")

            x_val, y_val = self._validation_data_cache

        decoder = DecoderFactory.get_decoder(self.input_format, self.input_config)

        for unsupervised_round_dataset in self.unsupervised_kafka_dataset:
            if len(unsupervised_round_dataset) == 0:
                continue

            unsupervised_round_dataset = unsupervised_round_dataset.map(lambda x, y: decoder.decode(x, y)).batch(training_settings['batch'])
            x_unlabeled = np.concatenate([x for x, y in unsupervised_round_dataset], axis=0)

            logging.info("Generating pseudo-labels for the current federated-round dataset: %d samples", len(x_unlabeled))

            predictions = model.predict(x_unlabeled)
            confidence_scores, pseudo_labels = self._generate_pseudo_labels(model, predictions)

            high_confidence_indices = confidence_scores >= training_settings['confidence']
            high_confidence_pseudo_labels = pseudo_labels[high_confidence_indices]
            high_confidence_unlabeled_data = x_unlabeled[high_confidence_indices]

            if len(high_confidence_pseudo_labels) == 0:
                logging.info("No high-confidence pseudo-labels found in the current federated round. Keeping the current model weights.")
                break

            logging.info("Found %d high-confidence pseudo-labels from %d unlabeled samples", len(high_confidence_pseudo_labels), len(x_unlabeled))

            if first_incremental_round:
                x_round_training = np.concatenate([x_train, high_confidence_unlabeled_data])
                y_round_training = np.concatenate([y_train, high_confidence_pseudo_labels])
                logging.info("Training with initial labeled data and current-round pseudo-labeled data")
            else:
                x_round_training = high_confidence_unlabeled_data
                y_round_training = high_confidence_pseudo_labels
                logging.info("Training only with current-round pseudo-labeled data")

            if 'N' not in training_settings:
                unsupervised_model_trained = model.fit(x_round_training, y_round_training, validation_data=(x_val, y_val), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])
            else:
                y_training = []
                y_validation = []

                for i in range(training_settings['N']):
                    y_training.append(y_round_training)
                    y_validation.append(y_val)

                unsupervised_model_trained = model.fit(x_round_training, y_training, validation_data=(x_val, y_validation), **self._get_array_fit_kwargs(training_settings), **training_settings['kwargs_val'])

            for key in self.model_trained.history.keys():
                self.model_trained.history[key].extend(unsupervised_model_trained.history[key])

        elapsed_time = time.time() - start

        logging.info("Model trained successfully. Elapsed time: [%f]", elapsed_time)

        return self.model_trained
    
    def save_metrics(self, model_trained):
        """Saves the metrics of single models"""

        epoch_training_metrics = {}
        epoch_validation_metrics = {}

        for k, v in model_trained.history.items():
            if not k.startswith("val_"):
                try:
                    epoch_training_metrics[k].append(v)
                except:
                    epoch_training_metrics[k] = v
            else:
                try:
                    epoch_validation_metrics[k[4:]].append(v)
                except:
                    epoch_validation_metrics[k[4:]] = v
        
        return epoch_training_metrics, epoch_validation_metrics