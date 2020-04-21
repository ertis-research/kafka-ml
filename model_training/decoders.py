import numpy as np
import tensorflow as tf
import tensorflow_io.kafka as kafka_io
import tensorflow_io as tfio
from utils import *

class DecoderFactory:
    """Factory class for the decoders"""

    @staticmethod
    def get_decoder(input_format, configuration):
        if input_format == 'RAW':
            return RawDecoder(configuration)
        elif input_format == 'AVRO':
            return AvroDecoder(configuration)
        else:
            raise ValueError(input_format)

class RawDecoder:
    """RAW class decoder implementation
        ARGS:
            configuration (dic): configuration properties
        Attributes:
            datatype(tensorflowtype): tensorflow type
            reshape: reshape of the data
            datatype (:obj:DType): output type of the train data
            reshape_x (:obj:array): reshape for training data (optional)
            labeltype (:obj:DType): output type of the label data
            reshape_y (obj:array): reshape for label data (optional)

    """
    def __init__(self, configuration):
        self.datatype = string_to_tensorflow_type(configuration['data_type'])
        self.x_reshape = configuration['data_reshape']
        if self.x_reshape is not None:
            self.x_reshape = np.fromstring(self.x_reshape, dtype=int, sep=' ')

        self.labeltype = string_to_tensorflow_type(configuration['label_type'])
        self.y_reshape = configuration['label_reshape']
        if self.y_reshape is not None:
            self.y_reshape = np.fromstring(self.y_reshape, dtype=int, sep=' ')
    
    def decode(self, x, y):
        return decode_input(x, y, self.datatype, self.x_reshape, self.labeltype, self.y_reshape)

class AvroDecoder:
    """AVRO class decoder implementation
        ARGS:
            configuration (dic): configuration properties
        Attributes:
            scheme(str): scheme of the AVRO implementation

    """
    def __init__(self, configuration):
        self.scheme = configuration['scheme']
    
    def decode(self, x, y):
        return tfio.experimental.serialization.decode_avro(x, schema=self.scheme).values()
    
