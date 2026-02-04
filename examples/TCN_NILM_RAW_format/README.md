# NILM and TCN

The following TCN TensorFlow deep learning model has been used in Kafka-ML for this example using the NILM dataset:

(Download the dataset from [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption))

```python
# Imports for model
from tensorflow.keras import layers, models, callbacks
from tensorflow.keras.layers import Add, SpatialDropout1D, Conv1D
```

```python
# Model code
def tcn_block(x, filters, kernel_size=3, dilation_rate=1):
    conv = Conv1D(filters, kernel_size, padding='causal',
                    dilation_rate=dilation_rate, activation='relu')(x)
    conv = SpatialDropout1D(0.2)(conv)
    res  = Conv1D(filters, 1, padding='same')(x)
    return Add()([res, conv])

def build_disaggregation_model(input_length=120, num_features=2, num_outputs=3):
    inp = layers.Input(shape=(input_length, num_features))
    x   = tcn_block(inp, 16, 3, 1)
    x   = tcn_block(x  ,  8, 3, 2)
    out = Conv1D(num_outputs, 1, padding='same', activation='linear')(x)
    model = models.Model(inp, out)
    model.compile("adam", loss='mse', metrics=['mae', 'mse', 'mape'])
    return model

model = build_disaggregation_model(120, 2, 3)
```

The batch_size used is 1024 and the training configuration (epochs=50, shuffle=True).