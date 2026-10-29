from confluent_kafka import Consumer

import time
import logging
import json
import time
import traceback

from decoders import *
from utils import load_federated_aggregation_environment_vars, load_federated_aggregator_params

from aggregators import get_aggregator, check_weights, aggregate_metrics
from FederatedKafkaMLModelSink import FederatedKafkaMLModelSink
from KafkaModelEngine import KafkaModelEngine

from singleFederatedIncrementalTraining import SingleFederatedIncrementalTraining
from distributedFederatedTraining import DistributedFederatedTraining
from distributedFederatedIncrementalTraining import DistributedFederatedIncrementalTraining

def collect_updates(consumer, training, expected_version, clients_per_round, min_clients_per_round, round_timeout):
  """Collects the models sent by the federated devices in the current round.

  The round finishes once clients_per_round updates have been received. If round_timeout (seconds) is greater
  than 0 and expires, the round finishes as soon as min_clients_per_round updates are available.
  In synchronous rounds (clients_per_round > 1), updates trained on another model version and repeated
  updates of the same device are discarded.
  """

  asynchronous = clients_per_round == 1
  updates, round_start, timeout_logged = [], time.time(), False

  while len(updates) < clients_per_round:
    if round_timeout > 0 and time.time() - round_start >= round_timeout:
      if len(updates) >= min_clients_per_round:
        logging.info("Round timeout reached with %d/%d updates. Aggregating the received ones", len(updates), clients_per_round)
        break
      if not timeout_logged:
        logging.warning("Round timeout reached with %d/%d updates. Waiting for at least %d updates", len(updates), clients_per_round, min_clients_per_round)
        timeout_logged = True

    message = consumer.poll(1.0)
    if message is None:
        continue
    if message.error():
        logging.info("Consumer error: {}".format(message.error()))
        continue

    try:
      control_msg = json.loads(message.value().decode('utf-8'))
      client = message.key().decode('utf-8') if message.key() is not None else None
      logging.info("Message received from client [%s] with version [%s]", client, control_msg['version'])

      if asynchronous:
        if expected_version != -1 and control_msg['version'] != -1:
          logging.info("Update staleness: %d", expected_version - control_msg['version'])
      else:
        if control_msg['version'] != expected_version:
          logging.info("Discarding update of client [%s] trained on another model version ([%s], expected [%s])", client, control_msg['version'], expected_version)
          continue
        if client is not None and any(update['client'] == client for update in updates):
          logging.info("Discarding repeated update of client [%s] in this round", client)
          continue

      model_reader = KafkaModelEngine(training.bootstrap_servers, 'server')
      weights = model_reader.getWeights(control_msg)
      check_weights(training.model.get_weights(), weights)
      logging.info("Model received from Federated devices")

      updates.append({
        'weights': weights,
        'num_data': control_msg.get('num_data'),
        'metrics': control_msg['metrics'],
        'version': control_msg['version'],
        'client': client
      })
      logging.info("Updates received in this round: %d/%d", len(updates), clients_per_round)

    except Exception as e:
      traceback.print_exc()
      logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))

  return updates

def EdgeBasedTraining(training):
    clients_per_round, min_clients_per_round, round_timeout = load_federated_aggregation_environment_vars()
    logging.info("Received federated aggregation information (clients_per_round, min_clients_per_round, round_timeout) ([%d], [%d], [%d])",
                 clients_per_round, min_clients_per_round, round_timeout)

    aggregator_params = load_federated_aggregator_params()
    aggregator = get_aggregator(training.agg_strategy, asynchronous=clients_per_round == 1, **aggregator_params)
    logging.info("Using %s aggregation (%s) with params %s", training.agg_strategy, 'asynchronous' if clients_per_round == 1 else 'synchronous', str(aggregator_params))
    """Loads the aggregation strategy before starting, so not implemented strategies fail fast"""

    training.get_models()
    """Downloads the models from the URLs received, saves and loads them from the filesystem to Tensorflow models"""

    if isinstance(training, DistributedFederatedTraining) or isinstance(training, DistributedFederatedIncrementalTraining):
      training.configure_distributed_models()
    """Distributed models configuration"""

    aggregator.configure(training.model)
    """Gives the global model to the aggregation strategy"""

    training.generate_and_send_data_standardization()
    """Generates the data standardization and sends it to the model control topic"""

    training.generate_federated_kafka_topics()
    """Generates the federated Kafka topics to receive the data from the federated nodes"""

    logging.info("Started Kafka consumer in [%s] topic", training.model_control_topic)
    consumer = Consumer({'bootstrap.servers': training.bootstrap_servers, 'group.id': 'group_id_'+training.federated_string_id ,'auto.offset.reset': 'earliest','enable.auto.commit': False})
    consumer.subscribe([training.aggregation_control_topic])
    """Starts a Kafka consumer to receive control information"""

    training_settings = {'batch': training.batch, 'kwargs_fit': training.kwargs_fit, 'kwargs_val': training.kwargs_val}

    if isinstance(training, (DistributedFederatedTraining, DistributedFederatedIncrementalTraining)):
      training_settings['N'] = training.N

    if training.unsupervised:
      training_settings['unsupervised'] = True
      training_settings['unsupervised_rounds'] = training.unsupervised_rounds
      training_settings['confidence'] = training.confidence
    else:
      training_settings['unsupervised'] = False

    if isinstance(training, (SingleFederatedIncrementalTraining, DistributedFederatedIncrementalTraining)):
      training_settings['stream_timeout'] = training.stream_timeout

    version, rounds, model_metrics, start_time = 0, 0, [], time.time()
    """Initializes the version, rounds, model metrics and start time"""

    sink = FederatedKafkaMLModelSink(bootstrap_servers=training.bootstrap_servers, topic=training.model_data_topic, control_topic=training.model_control_topic, federated_id=training.result_id, training_settings=training_settings)

    while rounds < training.agg_rounds:
      logging.info("Round: {}".format(rounds))

      sent_version = version if rounds < training.agg_rounds - 1 else -1
      sink.send_model(training.model, sent_version)
      logging.info("Model sent to Federated devices")

      expected_version = sent_version + 1 if sent_version != -1 else -1
      """Devices return the version received plus one, or -1 for the last round"""

      updates = collect_updates(consumer, training, expected_version, clients_per_round, min_clients_per_round, round_timeout)

      training.model.set_weights(aggregator.aggregate(training.model.get_weights(), updates))
      model_metrics.append(aggregate_metrics(updates))

      version += 1
      rounds += 1
      logging.info("Aggregation of %d updates completed. New model version: %d", len(updates), version)

      consumer.commit()

      train_metrics, val_metrics = training.parse_metrics(model_metrics)
      training.sendTempMetrics(train_metrics, val_metrics)
      """Sends the current metrics to the backend"""

    logging.info("Federated training finished. Sending final model to Kafka-ML Cloud")
    consumer.close()
    sink.close()

    end_time = time.time()
    elapsed_time = end_time - start_time
    logging.info("Total training time: %s", str(elapsed_time))

    logging.info("Taking last metrics per epoch")

    train_metrics, val_metrics = training.parse_metrics(model_metrics)
    logging.info("Epoch training metrics: %s", str(train_metrics))
    logging.info("Epoch validation metrics: %s", str(val_metrics))

    training.sendFinalMetrics(False, train_metrics, val_metrics, [], elapsed_time, None)
    logging.info("Sending final model and metrics to Kafka-ML Cloud")
    """Sends the final metrics to the backend"""

    logging.info("Edge-based training (%s) finished", type(training).__name__)
