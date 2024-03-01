from utils import *
import json
import tensorflow_io as tfio
import tensorflow_io.kafka as kafka_io
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import traceback
import requests
import logging
import re
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

class MainTraining(object):
    """Main class for training
    
    Attributes:
        bootstrap_servers (str): list of boostrap server for the Kafka connection
        result_url (str): URL for downloading the untrained model
        result_id (str): Result ID of the model
        control_topic(str): Control topic
        deployment_id (int): deployment ID of the application
        batch (int): Batch size used for training
        kwargs_fit (:obj:json): JSON with the arguments used for training
        kwargs_val (:obj:json): JSON with the arguments used for validation
    """

    def __init__(self):
        """Loads the environment information"""

        self.bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS')
        self.result_url = os.environ.get('RESULT_URL')
        self.result_id = os.environ.get('RESULT_ID')
        self.control_topic = os.environ.get('CONTROL_TOPIC')
        self.deployment_id = int(os.environ.get('DEPLOYMENT_ID'))
        self.batch = int(os.environ.get('BATCH'))
        self.kwargs_fit = json.loads(os.environ.get('KWARGS_FIT').replace("'", '"'))
        self.kwargs_val = json.loads(os.environ.get('KWARGS_VAL').replace("'", '"'))
        self.confussion_matrix = json.loads(os.environ.get('CONF_MAT_CONFIG').replace("'", '"'))
        self.model = None
        self.tensorflow_models = None

        logging.info("Received main environment information (bootstrap_servers, result_url, result_id, control_topic, deployment_id, batch, kwargs_fit, kwargs_val) ([%s], [%s], [%s], [%s], [%d], [%d], [%s], [%s])",
                self.bootstrap_servers, str(self.result_url), str(self.result_id), self.control_topic, self.deployment_id, self.batch, str(self.kwargs_fit), str(self.kwargs_val))

    def get_single_model(self):
        """Downloads the model and loads it"""

        download_model(self.result_url, PRE_MODEL_PATH, RETRIES, SLEEP_BETWEEN_REQUESTS)
        
        self.model = load_model(PRE_MODEL_PATH)

    def get_distributed_models(self):
        """Downloads the models and loads them"""

        PRE_MODEL_PATHS = []
        """Paths of the received pre-models"""
        for i, url in enumerate(self.result_url, start=1):
            path='pre_model_{}.h5'.format(i)
            PRE_MODEL_PATHS.append(path)

            download_model(url, path, RETRIES, SLEEP_BETWEEN_REQUESTS)

        tensorflow_models = []
        for path in PRE_MODEL_PATHS:
            tensorflow_models.append(load_model(path))

        self.tensorflow_models = tensorflow_models

    def generate_and_send_data_standardization(self, model_logger_topic, federated_string_id, data_restriction, min_data, distributed, incremental):
        """Generates and sends the data standardization"""
        
        input_shape = str(self.model.input_shape)
        output_shape = str(self.model.output_shape)

        input_shape_sub = (re.search(', (.+?)\)', input_shape))
        output_shape_sub = (re.search(', (.+?)\)', output_shape))

        if input_shape_sub:
            input_shape = input_shape_sub.group(1)
            input_shape = input_shape.replace(',','')
        if output_shape_sub:
            output_shape = output_shape_sub.group(1)
            output_shape = output_shape.replace(',','')
        
        model_data_standard = {
                'model_format':{'input_shape': input_shape,
                                'output_shape': output_shape,
                            },
                'federated_params': {
                            'federated_string_id': federated_string_id,
                            'data_restriction': data_restriction,
                            'min_data': min_data
                            },
                'framework': 'tf',
                'distributed': distributed,
                'incremental': incremental
                }
        
        logging.info("Model data standard: %s", model_data_standard)

        # Send model info to Kafka to notify that a new model is available
        prod = Producer({'bootstrap.servers': self.bootstrap_servers})

        # Send expected data standardization to Kafka
        prod.produce(model_logger_topic, json.dumps(model_data_standard))
        prod.flush()
        logging.info("Send the untrained model to Kafka Model Topic")
    
    def generate_federated_kafka_topics(self):
        # Generate the topics for the federated training
        self.model_control_topic = f'FED-{self.federated_string_id}-model_control_topic'
        self.model_data_topic = f'FED-{self.federated_string_id}-model_data_topic'
        self.aggregation_control_topic = f'FED-{self.federated_string_id}-agg_control_topic'
        
        # Set up the admin client
        admin_client = AdminClient({'bootstrap.servers': self.bootstrap_servers})

        topics_to_create = []

        # Create the new topics
        topics_to_create.append(NewTopic(self.model_control_topic, 1, config={'max.message.bytes': '50000'}))         # 50 KB    
        topics_to_create.append(NewTopic(self.aggregation_control_topic, 1, config={'max.message.bytes': '50000'}))   # 50 KB
        topics_to_create.append(NewTopic(self.model_data_topic, 1, config={'max.message.bytes': '10000000'}))         # 10 MB

        admin_client.create_topics(topics_to_create)

        # Wait for the topic to be created
        topic_created = False
        while not topic_created:
            topic_metadata = admin_client.list_topics(timeout=5)
            if self.model_control_topic in topic_metadata.topics and \
                    self.aggregation_control_topic in topic_metadata.topics and \
                    self.model_data_topic in topic_metadata.topics:
                
                topic_created = True
        
        logging.info("Federated topics created: (model_control_topic, aggregation_control_topic, model_data_topic) = ({}, {}, {})".format(
                                self.model_control_topic, self.aggregation_control_topic, self.model_data_topic))
    
    def parse_metrics(self, model_metrics):
        """Parse the metrics from the model"""

        epoch_training_metrics = {}
        epoch_validation_metrics = {}

        for agg_metrics in model_metrics:
            for keys in agg_metrics['training']:
                if keys not in epoch_training_metrics:
                    epoch_training_metrics[keys] = []
                epoch_training_metrics[keys].append(agg_metrics['training'][keys][-1])

                if keys not in epoch_validation_metrics:
                    epoch_validation_metrics[keys] = []
                epoch_validation_metrics[keys].append(agg_metrics['validation'][keys][-1])

        return epoch_training_metrics, epoch_validation_metrics
    
    def parse_distributed_metrics(self, model_metrics):
        """Parse the metrics from the model"""

        epoch_training_metrics = []
        epoch_validation_metrics = []
        
        for m in self.tensorflow_models:
            train_dic = {}
            val_dic = {}
            for agg_metrics in model_metrics:
                for keys in agg_metrics['training']:
                    if m.name in keys:
                        if keys[len(m.name)+1:] not in train_dic:
                            train_dic[keys[len(m.name)+1:]] = []
                        train_dic[keys[len(m.name)+1:]].append(agg_metrics['training'][keys][-1])

                        if keys[len(m.name)+1:] not in val_dic:
                            val_dic[keys[len(m.name)+1:]] = []
                        val_dic[keys[len(m.name)+1:]].append(agg_metrics['validation'][keys][-1])
            epoch_training_metrics.append(train_dic)
            epoch_validation_metrics.append(val_dic)

        return epoch_training_metrics, epoch_validation_metrics
    
    def get_train_data(self, kafka_topic, group, decoder):
        """Obtains the data and labels for training from Kafka

            Args:
            kafka_topic (str): Kafka topic
            group (str): Kafka group
            decoder(class): decoder to decode the data
            
            Returns:
            train_kafka: training data and labels from Kafka
        """
        logging.info("Starts receiving training data from Kafka servers [%s] with topics [%s]", self.bootstrap_servers, kafka_topic)
        train_data = kafka_io.KafkaDataset(kafka_topic.split(','), servers=self.bootstrap_servers, group=group, eof=True, message_key=True).map(lambda x, y: decoder.decode(x, y))

        return train_data

    def get_online_train_data(self, kafka_topic):
        """Obtains the data and labels incrementally for training from Kafka

            Args:
            kafka_topic (str): Kafka topic
            
            Returns:
            online_train_kafka: online training data and labels from Kafka
        """
        logging.info("Starts receiving online training data from Kafka servers [%s] with topics [%s], group [%s] and stream_timeout [%d]", self.bootstrap_servers, kafka_topic, self.result_id, self.stream_timeout)
        
        online_train_data = tfio.experimental.streaming.KafkaBatchIODataset(
            topics=[kafka_topic],
            group_id=self.result_id,
            servers=self.bootstrap_servers,
            stream_timeout=self.stream_timeout,
            configuration=None,
            internal=True
        )

        return online_train_data

    def split_dataset(self, data, kafka_dataset):
        """Splits the dataset for training, validation and test"""

        training_size = int((1-(data['validation_rate']+data['test_rate']))*(data['total_msg']))
        validation_size = int(data['validation_rate'] * data['total_msg'])
        test_size = int(data['test_rate'] * data['total_msg'])
        logging.info("Training batch size %d, validation batch size %d and test batch size %d", training_size, validation_size, test_size)

        train_dataset = kafka_dataset.take(training_size).batch(self.batch)
        """Splits dataset for training"""

        test_dataset = kafka_dataset.skip(training_size)

        if validation_size > 0 and test_size > 0:
            """If validation and test size are greater than 0, then split the dataset for validation and test"""
            validation_dataset = test_dataset.skip(test_size).batch(self.batch)
            test_dataset = test_dataset.take(test_size).batch(self.batch)
        elif validation_size > 0:
            """If only validation size is greater than 0, then split the dataset for validation"""
            validation_dataset = test_dataset.batch(self.batch)
            test_dataset = None
        elif test_size > 0:
            """If only test size is greater than 0, then split the dataset for test"""
            validation_dataset = None
            test_dataset = test_dataset.batch(self.batch)
        else:
            """If no validation or test size is greater than 0, then split the dataset for training"""
            validation_dataset = None
            test_dataset = None

        splits = {
            'train_dataset': train_dataset,
            'validation_dataset': validation_dataset,
            'test_dataset': test_dataset,
            'test_size': test_size
        }

        return splits
    
    def split_online_dataset(self, validation_rate, kafka_dataset):
        """Splits the online dataset for training and validation"""

        training_size = int((1-validation_rate)*len(kafka_dataset))
        validation_size = int(validation_rate*len(kafka_dataset))
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

    def create_distributed_model(self):
        """Creates a distributed model"""

        metrics = self.metrics.replace(' ', '')
        metrics = metrics.split(',')
        """Formats metrics"""

        outputs = []
        img_input = self.tensorflow_models[0].input
        outputs.append(self.tensorflow_models[0](img_input))
        for index in range(1, self.N):
            next_input = outputs[index-1]
            outputs.append(self.tensorflow_models[index](next_input[0]))
        """Obteins all the outputs from each distributed submodel"""

        predictions = []
        for index in range(0, self.N-1):
            s = outputs[index]
            predictions.append(s[1])
        predictions.append(outputs[-1])
        """Obteins all the prediction outputs from each distributed submodel"""

        model = keras.Model(inputs=[img_input], outputs=predictions, name='model')
        """Creates a global model consisting of all distributed submodels"""

        weights = {}
        for m in self.tensorflow_models:
            weights[m.name] = self.loss
        """Sets the loss"""

        learning_rates = []
        for index in range (0, self.N):
            learning_rates.append(self.learning_rate)
        """Sets the learning rate for each distributed model"""

        model.compile(optimizer=self.optimizer, loss=weights, metrics=metrics, loss_weights=learning_rates)
        """Compiles the global model"""

        self.model = model
    
    def train_classic_model(self, splits, callback):
        """Trains classic model"""

        model_trained = self.model.fit(splits['train_dataset'], validation_data=splits['validation_dataset'], **self.kwargs_fit, callbacks=[callback])

        training_results = {
            'model_trained': model_trained
        }

        return training_results

    def train_incremental_model(self, kafka_dataset, decoder, validation_rate, callback, start):
        """Trains incremental model"""

        for mini_ds in kafka_dataset:
            if len(mini_ds) > 0:
                mini_ds = mini_ds.map(lambda x, y: decoder.decode(x, y))
                splits = self.split_online_dataset(validation_rate, mini_ds)
                splits['train_dataset'] = splits['train_dataset'].batch(self.batch)
                if splits['validation_dataset'] is not None:
                    splits['validation_dataset'] = splits['validation_dataset'].batch(self.batch)
                model_trained = self.model.fit(splits['train_dataset'], validation_data=splits['validation_dataset'], **self.kwargs_fit, callbacks=[callback])
                if self.stream_timeout == -1:
                    if 'reference' not in locals() and 'reference' not in globals():
                        reference = model_trained.history['val_'+self.monitoring_metric][-1]
                    last = model_trained.history['val_'+self.monitoring_metric][-1]
                    if reference != last:
                        if (self.change == 'up' and last - reference >= self.improvement) or (self.change == 'down' and reference - last >= self.improvement):
                            dtime = time.time() - start
                            reference = last
                            epoch_training_metrics, epoch_validation_metrics, test_metrics = self.saveMetrics(model_trained)
                            self.sendMetrics(None, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, None)

        training_results = {
                'model_trained': model_trained
            }

        return training_results
    
    def saveSingleMetrics(self, model_trained):
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
        
        return epoch_training_metrics, epoch_validation_metrics, {}
    
    def saveDistributedMetrics(self, model_trained):
        """Saves the metrics of distributed models"""
        
        epoch_training_metrics = []
        epoch_validation_metrics = []

        for m in self.tensorflow_models:
            train_dic = {}
            val_dic = {}
            for k, v in model_trained.history.items():
                if m.name in k:
                    if not k.startswith("val_"):
                        try:
                            train_dic[k[len(m.name)+1:]].append(v)
                        except:
                            train_dic[k[len(m.name)+1:]] = v
                    else:
                        try:
                            val_dic[k[4+len(m.name)+1:]].append(v)
                        except:
                            val_dic[k[4+len(m.name)+1:]] = v
            epoch_training_metrics.append(train_dic)
            epoch_validation_metrics.append(val_dic)
        
        return epoch_training_metrics, epoch_validation_metrics, []
    
    def test_model(self, splits):
        """Tests model"""

        if splits['test_size'] > 0:
            logging.info("Model ready to test with configuration %s", str(self.kwargs_val))
            test = self.model.evaluate(splits['test_dataset'], **self.kwargs_val)
            """Validates the model"""
            logging.info("Model tested!")
            logging.info("Model test metrics: %s", str(test))
        
        return test
    
    def createConfussionMatrix(self, test_dataset, test_size):
        """Creates confussion matrix"""

        cf_generated = False
        cf_matrix = None
        
        if self.confussion_matrix and test_size > 0:
            try:
                logging.info("Trying to generate confussion matrix")

                test = self.model.predict(test_dataset, **self.kwargs_val)
                """Predicts test data on the trained model"""

                test = np.argmax(test, axis=1)
                """Arg max for each sub list"""
                                
                y_true = np.concatenate([y for _, y in test_dataset], axis=0)

                cf_matrix = confusion_matrix(y_true, test)
                """Generates the confussion matrix"""

                logging.info("Confussion matrix generated")

                sns.set(rc = {'figure.figsize':(10,8)})
                                
                lab = np.around(cf_matrix.astype('float') / cf_matrix.sum(axis=1)[:, np.newaxis], decimals=4)
                ax = sns.heatmap(lab, annot=True, fmt='.2%', cmap="Blues")

                ax.set_title('Confusion Matrix\n')
                ax.set_xlabel('\nPredicted Values\n')
                ax.set_ylabel('Real values')

                plt.savefig(CONFUSSION_MODEL_IMAGE, dpi=200, transparent=True)

                cf_generated = True
                logging.info("Generated confussion matrix successfully")
            except:
                logging.info("Could not generate confussion matrix")

        return cf_generated, cf_matrix
    
    def sendTempMetrics(self, train_metrics, val_metrics):
        """Send the metrics to the backend"""
        
        results = {
            'train_metrics': train_metrics,
            'val_metrics': val_metrics
        }

        url = self.result_url.replace('results', 'results_metrics')

        retry = 0
        finished = False
        while not finished and retry < RETRIES:
            try:
                data = {'data': json.dumps(results)}
                r = requests.post(url, data=data)
                if r.status_code == 200:
                    finished = True
                    logging.info("Metrics updated!")
                else:
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                    retry += 1
            except Exception as e:
                traceback.print_exc()
                retry += 1
                logging.error("Error sending the metrics to the backend [%s].", str(e))
                time.sleep(SLEEP_BETWEEN_REQUESTS)
    
    def sendDistributedTempMetrics(self, train_metrics, val_metrics):
        """Send the metrics to the backend"""

        results_list = []
        for i in range (len(self.tensorflow_models)):
            results = {
                      'train_metrics': train_metrics[i],
                      'val_metrics': val_metrics[i]
            }
            results_list.append(results)

        new_urls = []
        for url in self.result_url:
            new_urls.append(url.replace('results', 'results_metrics'))

        retry = 0
        finished = False
        while not finished and retry < RETRIES:
            try:
                responses = []
                for (result, url) in zip(results_list, new_urls):
                    data = {'data' : json.dumps(result)}
                    logging.info("Sending result data to backend")
                    r = requests.post(url, data=data)
                    responses.append(r.status_code)

                if responses[0] == 200 and len(set(responses)) == 1:
                    finished = True
                    logging.info("Metrics updated!")
                else:
                    time.sleep(SLEEP_BETWEEN_REQUESTS)
                    retry += 1
            except Exception as e:
                traceback.print_exc()
                retry += 1
                logging.error("Error sending the metrics to the backend [%s].", str(e))
                time.sleep(SLEEP_BETWEEN_REQUESTS)

    def sendSingleMetrics(self, cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix):
      """Sends single metrics to backend"""

      retry = 0
      finished = False

      datasource_received = False
      start_sending_results = time.time()
      
      while not finished and retry < RETRIES:
        try:
          self.model.save(TRAINED_MODEL_PATH)
          """Saves the trained model in the filesystem"""
                      
          files = {'trained_model': open(TRAINED_MODEL_PATH, 'rb'),
                  'confussion_matrix': open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}              

          if self.stream_timeout == -1:
            indefinite = True
          else:
            indefinite = False

          results = {
                  'train_metrics': epoch_training_metrics,
                  'val_metrics': epoch_validation_metrics,
                  'test_metrics': test_metrics,
                  'training_time': round(dtime, 4),
                  'confusion_matrix': cf_matrix.tolist() if cf_generated else None,
                  'indefinite': indefinite
          }

          data = {'data' : json.dumps(results)}
          logging.info("Sending result data to backend")
          r = requests.post(self.result_url, files=files, data=data)
          """Sends the training results to the backend"""

          if r.status_code == 200:
            finished = True
            datasource_received = True
            logging.info("Result data sent correctly to backend!!")
          else:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            retry+=1
        except Exception as e:
          traceback.print_exc()
          retry += 1
          logging.error("Error sending the result to the backend [%s].", str(e))
          time.sleep(SLEEP_BETWEEN_REQUESTS)
      
      end_sending_results = time.time()
      logging.info("Total time sending results: %s", str(end_sending_results - start_sending_results))

      return datasource_received
    
    def sendDistributedMetrics(self, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime):
      """Sends distributed metrics to backend"""

      retry = 0
      finished = False

      datasource_received = False
      start_sending_results = time.time()
      
      while not finished and retry < RETRIES:
        try:
          TRAINED_MODEL_PATHS = []
          for i in range (1, len(self.tensorflow_models)+1):
            path = 'trained_model_{}.h5'.format(i)
            TRAINED_MODEL_PATHS.append(path)

          for m, p in zip(self.tensorflow_models, TRAINED_MODEL_PATHS):
            m.save(p)
          """Saves the trained models in the filesystem"""

          files = []
          for p in TRAINED_MODEL_PATHS:
            files_dic = {'trained_model': open(p, 'rb'),
                        'confussion_matrix': None} # open(CONFUSSION_MODEL_IMAGE, 'rb') if cf_generated else None}
            files.append(files_dic)

          if self.stream_timeout == -1:
            indefinite = True
          else:
            indefinite = False

          results_list = []
          for i in range (len(self.tensorflow_models)):
            results = {
                      'train_metrics': epoch_training_metrics[i],
                      'val_metrics': epoch_validation_metrics[i],
                      'test_metrics': test_metrics[i] if test_metrics != [] else [],
                      'training_time': round(dtime, 4),
                      'confusion_matrix': None, # cf_matrix.tolist() if cf_generated else None
                      'indefinite': indefinite
            }
            results_list.append(results)

          responses = []
          for (result, url, f) in zip(results_list, self.result_url, files):
            data = {'data' : json.dumps(result)}
            logging.info("Sending result data to backend")
            r = requests.post(url, files=f, data=data)
            responses.append(r.status_code)
          """Sends the training results to the backend"""

          if responses[0] == 200 and len(set(responses)) == 1:
            finished = True
            datasource_received = True
            logging.info("Results data sent correctly to backend!!")
          else:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            retry += 1
        except Exception as e:
          traceback.print_exc()
          retry += 1
          logging.error("Error sending the result to the backend [%s].", str(e))
          time.sleep(SLEEP_BETWEEN_REQUESTS)
      
      end_sending_results = time.time()
      logging.info("Total time sending results: %s", str(end_sending_results - start_sending_results))

      return datasource_received