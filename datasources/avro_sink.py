
from .sink import KafkaMLSink

class AvroSink(KafkaMLSink):
    """Class representing a sink of Avro training data to Apache Kafka.

        Args:
            boostrap_servers (str): List of Kafka brokers
            topic (str): Kafka topic 
            deployment_id (str): Deployment ID for sending the training
            avro_filename (str): Filename of the AVRO data
            validation_rate (float): rate of the training data for evaluation. Defaults 0.3
            control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
                Defaults to control
            group_id (str): Group ID of the Kafka consumer. Defaults to sink

        Attributes:
            avro_filename (str): Filename of the AVRO data

    """

    def __init__(self, boostrap_servers, topic, deployment_id, 
        avro_filename, description='', validation_rate=0, control_topic='control', group_id='sink'):
        
        input_format='AVRO'
        super().__init__(boostrap_servers, topic, deployment_id, input_format, description,
            validation_rate, control_topic, group_id)
        self.avro_filename = avro_filename
        self.schema = avro.schema.Parse(open(self.avro_filename, "r").read())
        self.writer = DatumWriter(schema)
        self.bytes_writer = io.BytesIO()
        self.encoder = BinaryEncoder(bytes_writer)
    
    def send_avro(self, msg):
        self.writer.write(msg, self.encoder)
        raw_bytes = self.bytes_writer.getvalue()
        self.send_value(raw_bytes)