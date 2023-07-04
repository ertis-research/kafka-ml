# Federated Backend

This project provides the federated backend module for Kafka-ML Federated module. It has been implemented using the Python web framework [Django](https://www.djangoproject.com/) version 3.2.13. This project requires Python 3.5-3.8.

The Backend deploys Kubernetes components when deploying training and inference tasks. Therefore, it requires a running Kubernetes instance.

A brief introduction of most important files:
- File `automl/models.py` where the database tables (models) and their attributes are defined.
- File `automl/views.py` where it is implemented the RESTful API implementation through Views. A View can implement some HTTP methods (e.g., GET, POST)
- File `automl/serializers.py` serializers used to encode models to JSON and vice versa.
- File `automl/urls.py` mapping each RESTful View to a URL-path accessible in the Backend.
- File `autoweb/settings.py` main configuration file.

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

Once installed, run the commands `python manage.py makemigrations --noinput` and `python manage.py migrate --run-syncdb` to synchronize and create the database. We now use the single-file SQLite database, but you can change it to another one in the `settings.py` configuration file. 

After that, a new file called `db.sqlite3` will be created with the SQLite database. After a change in the `models.py` file, you should synchronize again the database with previous commands.

## Create a superuser
You can create a superuser to manage the models in the Web UI (/admin) provided by Django. Run `python manage.py createsuperuser` and fill up all the fields to create the superuser.

## Running development server

Run `python manage.py runserver 0.0.0.0:8085` for running the development server. Navigate to `http://localhost:8085/admin` to access the administration UI with your superuser credentials. You can change the IP and port when running the backend. 

Note that if you change the IP or port in development mode, you should also change the reference in the frontend to the new configuration (frontend/src/environments/environment.ts). Default: `localhost:8085`.

In development mode, you should also change the configuration for deploying Kubernetes components `automl/views.py` to be able to deploy Kubernetes components outside a Docker container, by default, this is only enabled inside a container. Comment the Kubernetes configuration as follows:

```
#config.load_incluster_config() # To run inside the container
config.load_kube_config() # To run externally
```

## Environments vars when deploying the backend in Kubernetes
- **KML_CLOUD_BOOTSTRAP_SERVERS**: list of Kafka bootstrap servers used in Kafka-ML cloud
- **FEDERATED_BOOTSTRAP_SERVERS**: list of Kafka bootstrap servers used in Kafka-ML Federated
- **DATA_CONTROL_TOPIC**: name of the Kafka control topic used in Kafka-ML federated for data tracking (from local Kafka)
- **MODEL_CONTROL_TOPIC**: name of the Kafka control topic used in Kafka-ML federated for model tracking (from cloud Kafka-ML)
- **TENSORFLOW_FEDERATED_TRAINING_MODEL_IMAGE**: name of the Docker TensorFlow federated training image to be deployed in Kubernetes
- **PYTORCH_FEDERATED_TRAINING_MODEL_IMAGE**: name of the Docker PyTorch federated training image to be deployed in Kubernetes
- **KUBE_NAMESPACE**: name of the Kubernetes namespace where the components will be deployed
- **BACKEND_URL**: URL and port of the Backend
- **ALLOWED_HOSTS**: list of allowed hosts for the Backend
- **DEBUG**: to enable (1) or disable (0) debug

## Running unit tests

Run `python manage.py test` to execute unit tests.
