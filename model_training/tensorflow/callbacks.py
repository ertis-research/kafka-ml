from utils import *
import json
import traceback
import requests

class SingleTrackTrainingCallback(keras.callbacks.Callback):
    """Callback for tracking the training of a single model"""

    def __init__(self, case, result_url, tensorflow_models):
        super().__init__()

        self.case = case
        self.url = result_url.replace('results', 'results_metrics')
        self.tensorflow_models = tensorflow_models
        
        self.epoch_training_metrics = {}
        self.epoch_validation_metrics = {}

    def __send_data(self, results, url):
        finished = False
        retry = 0
        
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
  
    def __prepare_train_data(self, logs):
        for k, v in logs.items():
            if not k.startswith("val_"):
                if not k in self.epoch_training_metrics.keys():
                    self.epoch_training_metrics[k] = [v]
                else:
                    self.epoch_training_metrics[k].append(v)
            else:
                if not k[4:] in self.epoch_validation_metrics.keys():
                    self.epoch_validation_metrics[k[4:]] = [v]
                else:
                    self.epoch_validation_metrics[k[4:]].append(v)
        
        results = {
                'train_metrics': self.epoch_training_metrics,
                'val_metrics': self.epoch_validation_metrics
        }

        self.__send_data(results, self.url)

    def __prepare_test_data(self, logs):
        for k, v in logs.items():
            if not k in self.epoch_validation_metrics.keys():
                self.epoch_validation_metrics[k] = [v]
            else:
                self.epoch_validation_metrics[k].append(v)
        
        results = {
                'train_metrics': self.epoch_training_metrics,
                'val_metrics': self.epoch_validation_metrics
        }

        self.__send_data(results, self.url)
  
    def on_epoch_end(self, epoch, logs=None):
        logging.info("Updating training metrics from epoch {}".format(epoch))
        self.__prepare_train_data(logs)

    def on_test_end(self, logs=None):
        if self.case == NOT_DISTRIBUTED_INCREMENTAL:
            logging.info("Updating validation metrics")
            self.__prepare_test_data(logs)
    
class DistributedTrackTrainingCallback(keras.callbacks.Callback):
    """Callback for tracking the training of a distributed model"""

    def __init__(self, case, result_url, tensorflow_models):
        super().__init__()
        
        self.case = case
        self.url = []
        for elem in result_url:
            self.url.append(elem.replace('results', 'results_metrics'))
        self.tensorflow_models = tensorflow_models
        
        self.epoch_training_metrics = []
        self.epoch_validation_metrics = []
        for i in range(len(self.tensorflow_models)):
            self.epoch_training_metrics.append({})
            self.epoch_validation_metrics.append({})

    def __send_data(self, results_list, url):
        finished = False
        retry = 0
        
        while not finished and retry < RETRIES:
            try:
                responses = []
                for (result, u) in zip(results_list, url):
                    data = {'data': json.dumps(result)}
                    r = requests.post(u, data=data)
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
  
    def __prepare_train_data(self, logs):
        for i, m in zip(range(len(self.tensorflow_models)), self.tensorflow_models):
            for k, v in logs.items():
                if m.name in k:
                    if not k.startswith("val_"):
                        if not k[len(m.name)+1:] in self.epoch_training_metrics[i].keys():
                            self.epoch_training_metrics[i][k[len(m.name)+1:]] = [v]
                        else:
                            self.epoch_training_metrics[i][k[len(m.name)+1:]].append(v)
                    else:
                        if not k[4+len(m.name)+1:] in self.epoch_validation_metrics[i].keys():
                            self.epoch_validation_metrics[i][k[4+len(m.name)+1:]] = [v]
                        else:
                            self.epoch_validation_metrics[i][k[4+len(m.name)+1:]].append(v)
        
        results_list = []
        for i in range(len(self.tensorflow_models)):
            results = {
                    'train_metrics': self.epoch_training_metrics[i],
                    'val_metrics': self.epoch_validation_metrics[i]
            }
            results_list.append(results)

        self.__send_data(results_list, self.url)

    def __prepare_test_data(self, logs):
        for i, m in zip(range(len(self.tensorflow_models)), self.tensorflow_models):
            for k, v in logs.items():
                if m.name in k:
                    if not k[len(m.name)+1:] in self.epoch_validation_metrics[i].keys():
                        self.epoch_validation_metrics[i][k[len(m.name)+1:]] = [v]
                    else:
                        self.epoch_validation_metrics[i][k[len(m.name)+1:]].append(v)
        
        results_list = []
        for i in range(len(self.tensorflow_models)):
            results = {
                    'train_metrics': self.epoch_training_metrics[i],
                    'val_metrics': self.epoch_validation_metrics[i]
            }
            results_list.append(results)

        self.__send_data(results_list, self.url)

    def on_epoch_end(self, epoch, logs=None):
        logging.info("Updating training metrics from epoch {}".format(epoch))
        self.__prepare_train_data(logs)

    def on_test_end(self, logs=None):
        if self.case == DISTRIBUTED_INCREMENTAL:
            logging.info("Updating validation metrics")
            self.__prepare_test_data(logs)