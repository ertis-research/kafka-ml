import numpy as np
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
        self.datatype = string_to_numpy_type(configuration['data_type'])
        self.x_reshape = configuration['data_reshape']
        if self.x_reshape is not None:
            self.x_reshape = np.fromstring(self.x_reshape, dtype=int, sep=' ')

        self.labeltype = string_to_numpy_type(configuration['label_type'])
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
        data_scheme(str): scheme of the AVRO implementation for data
        label_scheme(str): scheme of the AVRO implementation for label
    """
    def __init__(self, configuration):
        self.data_scheme = str(configuration['data_scheme']).replace("'", '"')
        self.label_scheme = str(configuration['label_scheme']).replace("'", '"')
    
    def decode(self, x, y):
        decode_x = tfio.experimental.serialization.decode_avro(x, schema=self.data_scheme)
        decode_y = tfio.experimental.serialization.decode_avro(y, schema=self.label_scheme)
      
        res_x= []
        for key in decode_x.keys():
            res_x.append(decode_x.get(key))
        
        res_y = []
        for key in decode_y.keys():
            res_y.append(decode_y.get(key))

        return (res_x, res_y)