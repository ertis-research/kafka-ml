from .sink import KafkaMLSink

class OnlineRawSink(KafkaMLSink):
    """Class representing an online sink of RAW training data to Apache Kafka.

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
            validation_rate (float): rate of the training data for validation. Defaults 0
            control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
                Defaults to KAFKA_ML_CONTROL_TOPIC
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
        data_type=None, label_type=None, description='', data_reshape=None, label_reshape=None, 
        validation_rate=0, control_topic='KAFKA_ML_CONTROL_TOPIC', group_id='sink', unsupervised_topic=None):
        
        input_format = 'RAW'
        test_rate = 0
        super().__init__(boostrap_servers, topic, deployment_id, input_format, description, {}, # {} = no data_restrictions
            validation_rate, test_rate, control_topic, group_id, unsupervised_topic)
        
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
        self._configured_format = self.data_type is not None

    def send(self, data, label):
        """Sends data and label to Apache Kafka"""
    
        if not self._configured_format:
            self.data_reshape = super().shape_to_string(data)
            self.label_reshape = super().shape_to_string(label)
            self.data_type = super().type_to_string(data)
            self.label_type = super().type_to_string(label)
            self._configured_format = True
            self.input_config = {
                'data_type' : self.data_type,
                'label_type': self.label_type,
                'data_reshape' : self.data_reshape,
                'label_reshape' : self.label_reshape,
            }
            if self.unsupervised_topic is None:
                super().send_online_control_msg()
        
        super().send(data.tobytes(), label.tobytes())
    
    def unsupervised_send(self, data):
        """Sends data to Apache Kafka"""
        
        super().unsupervised_send(data.tobytes())