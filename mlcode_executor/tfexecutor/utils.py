import tensorflow as tf
import numpy as np

def string_to_numpy_type(out_type):
    """Converts a string with the same name to a Numpy type.
    Acceptable types are half, float, double, int32, uint16, uint8,
                int16, int8, int64, string, bool.
    Args:
        out_type (str): Output type to convert
    Returns:
        Numpy DType: Numpy DType of the intput
    """
    if out_type == "half":
        return np.half
    elif out_type == "float":
        return np.float
    elif out_type == "float32":
        return np.float32
    elif out_type == "double":
        return np.double
    elif out_type == "int64":
        return np.int64
    elif out_type == "int32":
        return np.int32
    elif out_type == "int16":
        return np.int16
    elif out_type == "int8":
        return np.int8
    elif out_type == "uint16":
        return np.uint16
    elif out_type == "uint8":
        return np.uint8
    elif out_type == "string":
        return np.string
    elif out_type == "bool":
        return np.bool
    else:
        raise Exception("string_to_numpy_type: Unsupported type")


def decode_raw(x, output_type, output_reshape):
    """Decodes the raw data received from Kafka and reshapes it if needed.
    Args:
        x (raw): input data
        output_type (numpy type): output type of the received data
        reshape (array): reshape the numpy type (optional)
    Returns:
        DType: raw data to tensorflow model loaded
    """
    # res = np.frombuffer(x, dtype=output_type)
    # output_reshape = np.insert(output_reshape, 0, 1, axis=0)
    # res = res.reshape(*output_reshape)
    res = tf.io.decode_raw(x, out_type=output_type)
    res = tf.reshape(res, output_reshape)
    return res


def decode_input(x, y, output_type_x, reshape_x, output_type_y, reshape_y):
    """Decodes the input data received from Kafka and reshapes it if needed.
    Args:
        x (bytes): train data
        output_type_x (:obj:DType): output type of the train data
        reshape_x (:obj:`list`): reshape the tensorflow train data (optional)
        y (bytes): label data
        out_type_y (:obj:DType): output type of the label data
        reshape_y (:obj:`list`): reshape the tensorflow label data (optional)
    Returns:
        tuple: tuple with the (train, label) data received
    """
    x = decode_raw(x, output_type_x, reshape_x)
    y = decode_raw(y, output_type_y, reshape_y)
    return (x, y)
