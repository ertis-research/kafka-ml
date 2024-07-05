__author__ = 'Cristian Martin Fdez'

from kafka import KafkaConsumer, TopicPartition, KafkaProducer
import struct
import logging
import json

class KafkaMLSink(object):
    """Class representing a sink of training data to Apache Kafka. This class will allow to receive 
        training data in the send methods and will send it through Apache Kafka for the training and 
        validation purposes. Once all data would have been sent to Kafka, and the `close` method a 
        message will be sent to the control topic. 

    Args:
        boostrap_servers (str): List of Kafka brokers
        topic (str): Kafka topic 
        deployment_id (str): Deployment ID for sending the training
        input_format (str): Input format of the training data. Expected values are RAW and AVRO
        data_type (str): Datatype of the training data. Examples: uint8, string, bool, ...
        label_type (str): Datatype of the label data. Examples: uint8, string, bool, ...
        data_reshape (str): Reshape of the training data. Example: '28 28' for a matrix of 28x28. 
            Defaults '' for no dimension.
        label_reshape (str): Reshape of the label data. Example: '28 28' for a matrix of 28x28. 
            Defaults '' for no dimension.
        validation_rate (float): rate of the training data for evaluation. Defaults 0.2
        test_rate (float): rate of the training data for test. Defaults 0.1
        control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
            Defaults to control
        group_id (str): Group ID of the Kafka consumer. Defaults to sink

    Attributes:
        boostrap_servers (str): List of Kafka brokers
        topic (str): Kafka topic 
        deployment_id (str): Deployment ID for sending the training
        input_format (str): Input format of the training data. Expected values are RAW and AVRO
        data_type (str): Datatype of the training data. Examples: uint8, string, bool, ...
        label_type (str): Datatype of the label data. Examples: uint8, string, bool, ...
        data_reshape (str): Reshape of the training data. Example: '28 28' for a matrix of 28x28. 
            Defaults '' for no dimension.
        label_reshape (str): Reshape of the label data. Example: '28 28' for a matrix of 28x28. 
            Defaults '' for no dimension.
        validation_rate (float): rate of the training data for evaluation. Defaults 0.2
        test_rate (float): rate of the training data for test. Defaults 0.1
        control_topic (str): Control Kafka topic for sending confirmation after sending training data. 
            Defaults to KAFKA_ML_CONTROL_TOPIC
        group_id (str): Group ID of the Kafka consumer. Defaults to sink
        __partitions (:obj:dic): list of partitions and offssets of the self.topic received
        __consumer (:obj:KafkaConsumer): Kafka consumer
        __producer (:obj:KafkaProducer): Kafka producer
    """

    def __init__(self, boostrap_servers, topic, deployment_id,
        input_format, description='', dataset_restrictions={},
        validation_rate=0, test_rate=0, control_topic='KAFKA_ML_CONTROL_TOPIC', group_id='sink', unsupervised_topic=None):

        self.boostrap_servers = boostrap_servers
        self.topic = topic
        self.deployment_id = deployment_id
        self.input_format = input_format
        self.unsupervised_topic = unsupervised_topic
        if self.unsupervised_topic == '':
            self.unsupervised_topic = None
        self.description = description
        self.dataset_restrictions = dataset_restrictions
        self.validation_rate = validation_rate
        self.test_rate = test_rate
        self.control_topic = control_topic
        self.group_id = group_id
        self.total_messages = 0
        self.__partitions = {}
        self.__unsupervised_partitions = {}
        self.input_config = {}
        self.__consumer = KafkaConsumer(
            bootstrap_servers=self.boostrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False
        )
        self.__producer = KafkaProducer(
            bootstrap_servers=self.boostrap_servers,
            request_timeout_ms=60000,
        )
        self.__init_partitions()
        logging.info("Partitions received [%s]", str(self.__partitions))

    def __object_to_bytes(self, value):
        """Converts a python type to bytes. Types allowed are string, int, bool and float."""
        if value is None:
            return None
        elif value.__class__.__name__ == 'bytes':
            return value
        elif value.__class__.__name__ in ['int', 'bool']:
            return bytes([value])
        elif value.__class__.__name__ == 'float':
            return struct.pack("f", value)
        elif value.__class__.__name__ == 'str':
            return value.encode('utf-8')
        else:
            logging.error('Type %s not supported for converting to bytes', value.__class__.__name__)
            raise Exception("Type not supported")
            
    def __get_partitions_and_offsets(self, topic):
        """Obtains the partitions and offsets in the topic defined"""
        
        dic = {} 
        partitions = self.__consumer.partitions_for_topic(topic)
        if partitions is not None:
            for p in self.__consumer.partitions_for_topic(topic):
                tp = TopicPartition(topic, p)
                self.__consumer.assign([tp])
                self.__consumer.seek_to_end(tp)
                last_offset = self.__consumer.position(tp)
                dic[tp.partition] = {'offset': last_offset}
        return dic
    
    def __init_partitions(self):
        """Obtains the partitions and offsets in the topic defined and save them in self.__partitions"""
        
        self.__partitions = self.__get_partitions_and_offsets(self.topic)
        if self.unsupervised_topic is not None:
            self.__unsupervised_partitions = self.__get_partitions_and_offsets(self.unsupervised_topic)

    def __update_partitions(self, topic, partitions):
        """Updates the offsets and length in the topic defined after sending data"""
        
        dic = self.__get_partitions_and_offsets(topic)
        self.total_messages = 0
        for p in dic.keys():
            if p in partitions.keys():
                diff = dic[p]['offset'] - partitions[p]['offset']
                partitions[p]['length'] = dic[p]['offset']
            else:
                diff = dic[p]['offset']
                partitions[p] = {'offset': 0, 'length': dic[p]['offset']}
            self.total_messages += diff
        
        logging.info("%d messages have been sent to Kafka", self.total_messages)
    
    def __stringify_partitions(self, topic, partitions):
        """Stringify the partition information for sending to Apache Kafka"""
        
        res = ""
        for p in partitions.keys():
            """ Format topic:partition:offset:length,topic1:partition:offset:length"""
            res+= topic +":"+ str(p)+ ":" + str(partitions[p]['offset'])
            if 'length' in partitions[p]:
                res += ":" + str(partitions[p]['length'])
            res+=","
        
        res = res[:-1]
        """Remove last ',' list of topics"""

        return res

    def __send_control_msg(self):
        """Sends control message to Apache Kafka with the information"""

        dic = {
            'topic': self.__stringify_partitions(self.topic, self.__partitions),
            'unsupervised_topic': self.__stringify_partitions(self.unsupervised_topic, self.__unsupervised_partitions) if self.unsupervised_topic is not None else None,
            'input_format': self.input_format,
            'description' : self.description,
            'dataset_restrictions': self.dataset_restrictions,
            'input_config' : self.input_config,
            'validation_rate' : self.validation_rate,
            'test_rate' : self.test_rate,
            'total_msg': self.total_messages,
            'incremental': False
        }
        key = self.__object_to_bytes(self.deployment_id)
        data = json.dumps(dic).encode('utf-8')
        self.__producer.send(self.control_topic, key=key, value=data)
        self.__producer.flush()
        logging.info("Control message to Kafka %s", str(dic))
    
    def __send_online_control_msg(self):
        """Sends online control message to Apache Kafka with the information"""

        dic = {
            'topic': self.__stringify_partitions(self.topic, self.__partitions) if self.unsupervised_topic is not None else self.topic,
            'unsupervised_topic': self.unsupervised_topic,
            'input_format': self.input_format,
            'description' : self.description,
            'input_config' : self.input_config,
            'validation_rate' : self.validation_rate,
            'test_rate' : self.test_rate,
            'total_msg': self.total_messages if self.unsupervised_topic is not None else None,
            'dataset_restrictions': self.dataset_restrictions,
            'incremental': True
        }
        key = self.__object_to_bytes(self.deployment_id)
        data = json.dumps(dic).encode('utf-8')
        logging.info("Control topic %s and bootstrap server %s and groupid %s", self.control_topic, self.boostrap_servers, self.group_id)
        self.__producer.send(self.control_topic, key=key, value=data)
        self.__producer.flush()
        logging.info("Control message to Kafka %s", str(dic))
    
    def __send(self, data, label):
        """Converts data and label received to bytes and sends them to Apache Kafka"""
        
        data=self.__object_to_bytes(data)
        label=self.__object_to_bytes(label)
        if label is None:
            self.__producer.send(self.topic, data)
        else:
            self.__producer.send(self.topic, key=label, value=data)

    def __unsupervised_send(self, data):
        """Converts data received to bytes and sends it to Apache Kafka"""
        
        data=self.__object_to_bytes(data)
        label=self.__object_to_bytes(0)
        if self.unsupervised_topic is not None:
            self.__producer.send(self.unsupervised_topic, key=label, value=data)

    def __shape_to_string(self, out_shape):
        """Converts shape to string type.
        Args:
            out_shape (shape): Output shape to convert
        Returns:
            string: String shape of the input
        """

        if type(out_shape).__name__.startswith('tf.Tensor') or type(out_shape).__name__.startswith('ndarray'):
            return str(out_shape.shape).replace('(','').replace(',','').replace(')','')
        elif type(out_shape).__name__.startswith('list'):
            return str(len(out_shape))
        else:
            return '1'

    def __type_to_string(self, out_type):
        """Converts DType to string type.
        Args:
            out_type (DType): Output type to convert
        Returns:
            string: String DType of the input
        """
        
        while type(out_type).__name__.startswith('tf.Tensor') or type(out_type).__name__.startswith('ndarray'):
           out_type = out_type[0]

        if type(out_type).__name__.startswith('tf'):
           out_type = out_type.numpy().item()

        return type(out_type).__name__

    def send_online_control_msg(self):
        """Sends online control message to Apache Kafka with the information"""
        
        if self.unsupervised_topic is not None:
            self.__update_partitions(self.topic, self.__partitions)
        self.__send_online_control_msg()
    
    def shape_to_string(self, out_shape):
        """Converts shape to string type"""

        return self.__shape_to_string(out_shape)

    def type_to_string(self, out_type):
        """Converts DType to string type"""
        
        return self.__type_to_string(out_type)
    
    def send(self, data, label):
        """Sends data and label to Apache Kafka"""
        
        self.__send(data, label)

    def unsupervised_send(self, data):
        """Sends data to Apache Kafka"""
        
        self.__unsupervised_send(data)

    def send_value(self, data):
        """Sends data to Apache Kafka"""
        
        self.__send(data, None)

    def send_control_msg(self):
        """Sends control message to Apache Kafka with the information"""
        self.__send_control_msg()

    def online_close(self):
        """Closes the connection with Kafka"""
        
        self.__producer.flush()
        self.__producer.close()
        self.__consumer.close(autocommit=False)

    def close(self):
        """Closes the connection with Kafka and sends the control message to the control topic"""

        self.__producer.flush()
        if self.unsupervised_topic is not None:
            self.__update_partitions(self.unsupervised_topic, self.__unsupervised_partitions)
        self.__update_partitions(self.topic, self.__partitions)
        self.__send_control_msg()
        self.__producer.close()
        self.__consumer.close(autocommit=False)