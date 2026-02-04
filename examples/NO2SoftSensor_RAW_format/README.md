# River Water Quality Monitoring Dataset Example

This example uses the [River Water Quality Monitoring 1990 to 2018](https://data.europa.eu/data/datasets/river-water-quality-monitoring-1990-to-2018?locale=es) dataset in Kafka-ML with a TensorFlow deep learning model.

```python
model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(128, input_shape=(4,), activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1),
      ])
model.compile(optimizer='adam', loss='huber', metrics=['mae', 'mape', 'mse'])
```

The batch_size used is 16 and the training configuration (epochs=32, shuffle=True).