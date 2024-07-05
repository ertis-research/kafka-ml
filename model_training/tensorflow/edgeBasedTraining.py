from confluent_kafka import Consumer

import time
import logging
import json
import time
import traceback

from decoders import *

from FederatedKafkaMLModelSink import FederatedKafkaMLModelSink
from KafkaModelEngine import KafkaModelEngine

from singleFederatedIncrementalTraining import SingleFederatedIncrementalTraining
from distributedFederatedTraining import DistributedFederatedTraining
from distributedFederatedIncrementalTraining import DistributedFederatedIncrementalTraining

def aggregate_model(model, trained_model, aggregation_strategy, control_msg, model_metrics):
  """Aggregates the model with the trained model"""

  if aggregation_strategy == 'FedAvg':
    weights = [model.get_weights(), trained_model.get_weights()]
    new_weights = list()
    for weights_list_tuple in zip(*weights): 
        new_weights.append(
            np.array([np.array(w).mean(axis=0) for w in zip(*weights_list_tuple)])
        )
      
    model.set_weights(new_weights)

    model_metrics.append(control_msg['metrics'])

  elif aggregation_strategy == 'FedAvg+':
    # Weighted FedAvg: se hace un promedio de los modelos, pero se le da mas peso a los modelos mas recientes
    raise NotImplementedError
  elif aggregation_strategy == 'Another':
    raise NotImplementedError
  else:
    raise Exception('Aggregation strategy not implemented')
  
  version = control_msg['version']

  return model, version, model_metrics

def EdgeBasedTraining(training):
    training.get_models()
    """Downloads the models from the URLs received, saves and loads them from the filesystem to Tensorflow models"""

    if isinstance(training, DistributedFederatedTraining) or isinstance(training, DistributedFederatedIncrementalTraining):
      training.configure_distributed_models()
    """Distributed models configuration"""
    
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

      sink.send_model(training.model, version if rounds < training.agg_rounds - 1 else -1)
      logging.info("Model sent to Federated devices")
            
      got_aggregation = False
      while not got_aggregation:
        message = consumer.poll(1.0)
        if message is None:
            continue
        if message.error():
            logging.info("Consumer error: {}".format(message.error()))
            continue

        try:
          control_msg = json.loads(message.value().decode('utf-8'))
          logging.info("Message received for prediction")

          model_reader = KafkaModelEngine(training.bootstrap_servers, 'server')
          trained_model = model_reader.setWeights(training.model, control_msg)
          logging.info("Model received from Federated devices")

          training.model, version, model_metrics = aggregate_model(training.model, trained_model, training.agg_strategy, control_msg, model_metrics)
          logging.info("Aggregation completed. New model version: {}".format(version))

          rounds += 1

          consumer.commit()
          got_aggregation = True

          train_metrics, val_metrics = training.parse_metrics(model_metrics)
          training.sendTempMetrics(train_metrics, val_metrics)
          """Sends the current metrics to the backend"""

        except Exception as e:
          traceback.print_exc()
          logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))

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