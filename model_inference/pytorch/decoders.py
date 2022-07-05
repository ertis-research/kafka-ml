import numpy as np
from utils import *
import avro.schema
import io
from avro.io import DatumReader, BinaryDecoder

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
        self.datatype = configuration['data_type']
        self.reshape = configuration['data_reshape']
        if self.reshape != None and self.reshape != '':
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

    # Decode messages
    def avro_decoder(msg_value, reader):
        message_bytes = io.BytesIO(msg_value)
        decoder = BinaryDecoder(message_bytes)
        event_dict = reader.read(decoder)
        return event_dict
    
    def decode(self, x, y):
        reader_x = DatumReader(self.data_scheme)

        decode_x = self.avro_decoder(x, reader_x)
      
        res= []
        for key in decode_x.keys():
            res.append(decode_x.get(key))
        

        return res