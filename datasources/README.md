# Data sources

This folder contains the clients that can be used to send data streams to Apache Kafka in Kafka-ML using Avro and RAW formats. 

To use the following clients, you should install the python libraries by running `python -m pip install -r requirements.txt`.
- `avro_sink.py` client to send data stream training data using Avro. This client requires the definition of two Avro schemes for label and data.
- `raw_sink.py` client to send data stream training data using RAW format.
- `sink.py` base file used by avro and raw sinks.
- `avro_inference.py` client to send data stream inference data using Avro. This client requires the definition of a Avro scheme for data.