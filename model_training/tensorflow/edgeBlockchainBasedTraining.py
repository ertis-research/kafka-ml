import time
import logging
import json
import traceback
import numpy as np

from decoders import *

from FederatedKafkaMLModelSink import FederatedKafkaMLModelSink
from KafkaModelEngine import KafkaModelEngine

# TODO: Implement Incremental and Distributed Blockchain Federated Training if needed or going to be implemented
# from singleFederatedIncrementalTraining import SingleBlockchainFederatedIncrementalTraining
# from distributedFederatedTraining import DistributedBlockchainFederatedTraining
# from distributedFederatedIncrementalTraining import DistributedBlockchainFederatedIncrementalTraining

def aggregate_model(model, trained_model, aggregation_strategy, control_msg):
  """Aggregates the model with the trained model"""

  if aggregation_strategy == 'FedAvg':
    weights = [model.get_weights(), trained_model.get_weights()]
    new_weights = list()
    for weights_list_tuple in zip(*weights): 
        new_weights.append(
            np.array([np.array(w).mean(axis=0) for w in zip(*weights_list_tuple)])
        )
      
    model.set_weights(new_weights)

  elif aggregation_strategy == 'FedAvg+':
    # Weighted FedAvg: se hace un promedio de los modelos, pero se le da mas peso a los modelos mas recientes
    raise NotImplementedError
  elif aggregation_strategy == 'Another':
    raise NotImplementedError
  else:
    raise NotImplementedError('Aggregation strategy not implemented')
  
  return model

def EdgeBlockchainBasedTraining(training):
    training.get_models()
    """Downloads the models from the URLs received, saves and loads them from the filesystem to Tensorflow models"""

    # TODO: Implement Incremental and Distributed Blockchain Federated Training if needed
    # if isinstance(training, DistributedFederatedTraining) or isinstance(training, DistributedFederatedIncrementalTraining):
    #   training.configure_distributed_models()
    # """Distributed models configuration"""
    
    training.generate_and_send_data_standardization()
    """Generates the data standardization and sends it to the model control topic"""

    training.generate_federated_kafka_topics()
    """Generates the federated Kafka topics to receive the data from the federated nodes"""
  
    training_settings = {'batch': training.batch, 'kwargs_fit': training.kwargs_fit, 'kwargs_val': training.kwargs_val}
    
    # TODO: Implement Incremental and Distributed Blockchain Federated Training if needed
    # if isinstance(training, SingleFederatedIncrementalTraining):
    #   training_settings['stream_timeout'] = training.stream_timeout
    #   training_settings['monitoring_metric'] = training.monitoring_metric
    #   training_settings['change'] = training.change
    #   training_settings['improvement'] = training.improvement
    # elif isinstance(training, DistributedFederatedTraining):
    #   training_settings['optimizer'] = training.optimizer
    #   training_settings['learning_rate'] = training.learning_rate
    #   training_settings['loss'] = training.loss
    #   training_settings['metrics'] = training.metrics
    # elif isinstance(training, DistributedFederatedIncrementalTraining):
    #   training_settings['stream_timeout'] = training.stream_timeout
    #   training_settings['monitoring_metric'] = training.monitoring_metric
    #   training_settings['change'] = training.change
    #   training_settings['improvement'] = training.improvement
    #   training_settings['optimizer'] = training.optimizer
    #   training_settings['learning_rate'] = training.learning_rate
    #   training_settings['loss'] = training.loss
    #   training_settings['metrics'] = training.metrics

    rounds, model_metrics, start_time = 0, [], time.time()
    last_client_model_topic = None
    clients_contributions = dict()
    """Initializes the version, rounds, model metrics and start time"""

    sink = FederatedKafkaMLModelSink(bootstrap_servers=training.bootstrap_servers, topic=training.model_data_topic, control_topic=training.model_control_topic, federated_id=training.result_id, training_settings=training_settings)
    
    while rounds < training.agg_rounds:
      logging.info("Round: {}".format(rounds))

      control_msg = sink.send_model(training.model, rounds)
      logging.info("Model sent to Federated devices")
      
      if rounds == 0:
        training.save_model_architecture(json.dumps(control_msg['training_settings']), control_msg['model_architecture'], json.dumps(control_msg['model_compile_args']))
      else:
        training.save_update_along_with_global_model(last_client_model_topic, control_msg['topic'])

      training.write_control_message_into_blockchain(control_msg['topic'], rounds)
      logging.info("Waiting for Federated devices to send their models and blockchain confirmation")      
      
      while training.elements_to_aggregate() < 1:
        continue
      
      logging.info("A federated device sent its model. Aggregating models")

      last_client_model_topic, metrics, client_account, client_data_size = training.retrieve_last_model_from_queue()


      logging.info("Model received from client [%s], data size [%s] at round [%s] with metrics [%s]", client_account, client_data_size, rounds, metrics)

      try:
        control_msg = {
                        'topic': last_client_model_topic,
                        'metrics': metrics,
                        'account': client_account,
                        'num_data': client_data_size
                      }
        
        logging.info("Message received for prediction")

        model_reader = KafkaModelEngine(training.bootstrap_servers, 'server')
        trained_model = model_reader.setWeights(training.model, control_msg)
        logging.info("Model received from Federated devices")
        
        training.model = aggregate_model(training.model, trained_model, training.agg_strategy, control_msg)
        model_metrics.append(metrics)
        logging.info("Aggregation completed. New model version: {}".format(rounds))

        train_metrics, val_metrics = training.parse_metrics(model_metrics)
        training.sendTempMetrics(train_metrics, val_metrics)
        """ Sends the current metrics to the backend"""

        clients_contributions[client_account] = client_data_size
        training.calculate_reward(rounds, control_msg, clients_contributions)

        rounds += 1

      except Exception as e:
        traceback.print_exc()
        logging.error("Error with the received data [%s]. Waiting for new a new prediction.", str(e))

    # Saving last round update and sending final model
    if rounds > 0:
      training.save_update_along_with_global_model(last_client_model_topic, control_msg['topic'])
      training.write_control_message_into_blockchain(control_msg['topic'], rounds)

    logging.info("Federated training finished. Sending final model to Kafka-ML Cloud and stopping smart contract")
    sink.close()

    training.send_stopTraining()

    training.reward_participants()

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