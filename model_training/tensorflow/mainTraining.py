from utils import *
import json
import tensorflow_io as tfio
import tensorflow_io.kafka as kafka_io
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import traceback
import requests

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
        logging.info("Starts receiving online training data from Kafka servers [%s] with topics [%s], group [%s], stream_timeout [%d] and message_poll_timeout [%d]", self.bootstrap_servers,  kafka_topic, self.result_id, self.stream_timeout, self.message_poll_timeout)
        
        online_train_data = tfio.experimental.streaming.KafkaBatchIODataset(
            topics=[kafka_topic],
            group_id=self.result_id,
            servers=self.bootstrap_servers,
            stream_timeout=self.stream_timeout,
            message_poll_timeout=self.message_poll_timeout,
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
            'model_trained': model_trained,
            'incremental_validation': {}
        }

        return training_results
        
    def train_incremental_model(self, kafka_dataset, decoder, callback, start):
        """Trains incremental model"""

        incremental_validation = {}
        test_dataset = None
        test_size = 0
        counter = 0

        for mini_ds in kafka_dataset:
            mini_ds = mini_ds.map(lambda x, y: decoder.decode(x, y)).batch(self.batch)
            if len(mini_ds) > 0:
                counter += 1
                if counter < self.denominatorBatch - self.numeratorBatch:
                    model_trained = self.model.fit(mini_ds, **self.kwargs_fit, callbacks=[callback])
                elif counter < self.denominatorBatch:
                    aux_val = self.model.evaluate(mini_ds, **self.kwargs_val, callbacks=[callback])
                    if incremental_validation == {}:
                        for k, i in zip(model_trained.history.keys(), range(len(model_trained.history.keys()))):
                            incremental_validation[k] = [aux_val[i]]
                        if self.stream_timeout == -1:
                            reference = incremental_validation[self.monitoring_metric][0]
                    else:
                        for k, i in zip(incremental_validation.keys(), range(len(incremental_validation.keys()))):
                            incremental_validation[k].append(aux_val[i])
                        if self.stream_timeout == -1:
                            if (self.change == 'up' and incremental_validation[self.monitoring_metric][-1] - reference >= self.improvement) or (self.change == 'down' and reference - incremental_validation[self.monitoring_metric][-1] >= self.improvement):
                                dtime = time.time() - start
                                reference = incremental_validation[self.monitoring_metric][-1]
                                cf_generated, cf_matrix = self.createConfussionMatrix(test_dataset, test_size)
                                epoch_training_metrics, epoch_validation_metrics, test_metrics = self.saveMetrics(model_trained, incremental_validation)
                                self.sendMetrics(cf_generated, epoch_training_metrics, epoch_validation_metrics, test_metrics, dtime, cf_matrix)
                    if test_dataset == None:
                        test_dataset = mini_ds
                    else:
                        test_dataset = test_dataset.concatenate(mini_ds)
                elif counter == self.denominatorBatch:
                    counter = 0
                    model_trained = self.model.fit(mini_ds, **self.kwargs_fit, callbacks=[callback])
        if test_dataset != None:
            test_dataset = test_dataset.batch(self.batch)
            test_size = len(test_dataset)
            
        training_results = {
                'model_trained': model_trained,
                'incremental_validation': incremental_validation,
                'test_dataset': test_dataset,
                'test_size': test_size
            }

        return training_results
    
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