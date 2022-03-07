# TensorFlow Executor

This project provides the TensorFlow code Executor for Kafka-ML. It has been implemented using the Python web framework [Flask](https://flask.palletsprojects.com/en/2.0.x/) version 2.0.2. This project requires Python 3.5-3.8.

The file `app.py` is the important file here. It has implemented the RESTful API implementation through Views. A View can implement some HTTP methods (e.g., GET, POST).

## Installation for local development
Run `python -m pip install -r requirements.txt` to install the dependencies used by this module. 

## Running server

Run `gunicorn app:app --bind 0.0.0.0:8001 --timeout 0` for running the development server. You can change the IP and port when running the back-end. 

Note that if you change the IP or port in development mode, you should also change the reference in the backend deployment.
