import numpy as np
import tensorflow as tf
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
            datatype(numpytype): numpy type
            reshape: reshape of the data

    """
    def __init__(self, configuration):
        self.datatype = string_to_numpy_type(configuration['data_type'])
        self.reshape = configuration['data_reshape']
        if self.reshape is not None:
            self.reshape = np.fromstring(self.reshape, dtype=int, sep=' ')
    
    def decode(self, msg):
        return decode_raw(msg, self.datatype, self.reshape)

class AvroDecoder:
    """AVRO class decoder implementation
        ARGS:
            configuration (dic): configuration properties
        Attributes:
            scheme(str): scheme of the AVRO implementation

    """
    def __init__(self, configuration):
        self.data_scheme = str(configuration['data_scheme']).replace("'", '"')
    
    def decode(self, msg):
        decode_x = tfio.experimental.serialization.decode_avro(msg, schema=self.data_scheme)
      
        res= []
        for key in decode_x.keys():
            res.append(decode_x.get(key))
        
        return res
    
