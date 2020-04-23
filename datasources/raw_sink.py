
from .sink import KafkaMLSink

class RawSink(KafkaMLSink):
    """Class representing a sink of RAW training data to Apache Kafka.

        Args:
            boostrap_servers (str): List of Kafka brokers
            topic (str): Kafka topic 
            deployment_id (str): Deployment ID for sending the training
            data_type (str): Datatype of the training data. Examples: uint8, string, bool, ...
            label_type (str): Datatype of the label data. Examples: uint8, string, bool, ...
            data_reshape (str): Reshape of the training data. Example: '28 28' for a matrix of 28x28. 
                Defaults '' for no dimension.
            label_reshape (str): Reshape of the label data. Example: '28 28' for a matrix of 28x28. 
                Defaults '' for no dimension.
            validation_rate (float): rate of the training data for evaluation. Defaults 0.3
            control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
                Defaults to control
            group_id (str): Group ID of the Kafka consumer. Defaults to sink

        Attributes:
            data_type (str): Datatype of the training data. Examples: uint8, string, bool, ...
            label_type (str): Datatype of the label data. Examples: uint8, string, bool, ...
            data_reshape (str): Reshape of the training data. Example: '28 28' for a matrix of 28x28. 
                Defaults '' for no dimension.
            label_reshape (str): Reshape of the label data. Example: '28 28' for a matrix of 28x28. 
                Defaults '' for no dimension.

    """

    def __init__(self, boostrap_servers, topic, deployment_id,
        data_type, label_type, description='', data_reshape='', label_reshape='', 
        validation_rate=0, control_topic='control', group_id='sink'):
        
        input_format='RAW'
        super().__init__(boostrap_servers, topic, deployment_id, input_format, description,
            validation_rate, control_topic, group_id)
        
        self.data_type = data_type
        self.label_type = label_type
        self.data_reshape = data_reshape
        self.label_reshape = label_reshape
        self.input_config =  {
            'data_type' : self.data_type,
            'label_type': self.label_type,
            'data_reshape' : self.data_reshape,
            'label_reshape' : self.label_reshape,
        }