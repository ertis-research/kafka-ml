
from .sink import KafkaMLSink
import avro.schema
import io
from avro.io import DatumWriter, BinaryEncoder

class AvroSink(KafkaMLSink):
    """Class representing a sink of Avro training data to Apache Kafka.

        Args:
            boostrap_servers (str): List of Kafka brokers
            topic (str): Kafka topic 
            deployment_id (str): Deployment ID for sending the training
            data_scheme_filename (str): Filename of the AVRO scheme for training data
            label_scheme_filename (str): Filename of the AVRO scheme for label data
            validation_rate (float): rate of the training data for evaluation. Defaults 0
            test_rate (float): rate of the training data for test. Defaults 0
            control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
                Defaults to control
            group_id (str): Group ID of the Kafka consumer. Defaults to sink

    """

    def __init__(self, boostrap_servers, topic, deployment_id, 
        data_scheme_filename, label_scheme_filename, description='', validation_rate=0, test_rate=0, control_topic='control', group_id='sink'):
        
        input_format='AVRO'
        super().__init__(boostrap_servers, topic, deployment_id, input_format, description,
            validation_rate, test_rate, control_topic, group_id)
        
        self.data_scheme_filename = data_scheme_filename

        self.data_schema = open(self.data_scheme_filename, "r").read()

        self.avro_data_schema = avro.schema.Parse(self.data_schema)
        self.data_writer = DatumWriter(self.avro_data_schema)
        
        self.label_scheme_filename = label_scheme_filename
        self.label_schema = open(self.label_scheme_filename, "r").read()

        self.avro_label_schema = avro.schema.Parse(self.label_schema)
        self.label_writer = DatumWriter(self.avro_label_schema)

        self.data_io = io.BytesIO()
        self.label_io = io.BytesIO()
        self.data_encoder = BinaryEncoder(self.data_io)
        self.label_encoder = BinaryEncoder(self.label_io)

        self.input_config =  {
            'data_scheme' : self.data_schema,
            'label_scheme': self.label_schema,
        }
    
    def send_avro(self, data, label):
        self.data_writer.write(data, self.data_encoder)
        data_bytes = self.data_io.getvalue()
        
        self.label_writer.write(label, self.label_encoder)
        label_bytes = self.label_io.getvalue()

        self.send(data_bytes, label_bytes)
        """Sends the avro data"""
        
        self.data_io.seek(0)
        self.data_io.truncate(0)
        """Cleans data buffer"""

        self.label_io.seek(0)
        self.label_io.truncate(0)
        """Cleans label buffer"""