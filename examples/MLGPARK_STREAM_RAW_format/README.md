# Malaga Parking Occupance prediction

The following TensorFlow deep learning model has been used in Kafka-ML for this example using the Malaga Parking Occupance dataset:

```
model = tf.keras.models.Sequential([ 
    tf.keras.layers.Dense(256, activation='relu', input_shape=(6,)), 
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(1)
  ])
model.compile(optimizer='sgd',
    loss='mae', 
    metrics=['mae', 'mse'])
```
The batch_size used is 16 and the training configuration (epochs=25, shuffle=True).

In the PyTorch Case, the following deep learning model has been used in Kafka-ML for the Malaga Parking Occupance dataset example:

```
class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(6, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(self, x):
        return self.linear_relu_stack(x)

    def loss_fn(self):
        return nn.L1Loss()

    def optimizer(self):
        return torch.optim.SGD(model.parameters(), lr=1e-3)

    def metrics(self):
        val_metrics = {
            "mse": MeanSquaredError(),
            "loss": Loss(self.loss_fn())
         }
        return val_metrics

model = NeuralNetwork()
```
The batch_size used is 16 and the training configuration (max_epochs=25, shuffle=True)