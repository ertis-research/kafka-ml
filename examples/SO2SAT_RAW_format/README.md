# SO2SAT and VGG16

The following VGG16 TensorFlow deep learning model has been used in Kafka-ML for this example using the SO2SAT dataset:

```
base_model = tf.keras.applications.VGG16(include_top=False, weights='imagenet', input_shape=(32,32,3))
x = tf.keras.layers.Flatten()(base_model.output)
x = tf.keras.layers.Dense(1000, activation='relu')(x)
x = tf.keras.layers.Dense(512, activation='relu')(x)
x = tf.keras.layers.Dense(128, activation='relu')(x)
predictions = tf.keras.layers.Dense(17, activation = 'softmax')(x)

model = tf.keras.Model(inputs = base_model.input, outputs = predictions)

model.compile(optimizer=tf.keras.optimizers.SGD(0.001),
      loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), 
      metrics=[tf.keras.metrics.SparseCategoricalAccuracy()])
```
The batch_size used is 256 and the training configuration (epochs=50, shuffle=True).

In the PyTorch Case, the following VGG16 deep learning model has been used in Kafka-ML for the SO2SAT dataset example:

```
class VGG16(nn.Module):
    def __init__(self):
        super(VGG16, self).__init__()
        self.pretrained = models.vgg16(pretrained=True)
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(1000, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 17),
            nn.Softmax()
        )
        
    def forward(self, x):
        x = self.pretrained(x)
        x = self.flatten(x)
        output = self.linear_relu_stack(x)
        return output

    def loss_fn(self):
        return nn.CrossEntropyLoss()

    def optimizer(self):
        return torch.optim.SGD(model.parameters(), lr=1e-3)

    def metrics(self):
        val_metrics = {
            "accuracy": Accuracy(),
            "loss": Loss(self.loss_fn())
         }
        return val_metrics

model = VGG16()
```
The batch_size used is 256 and the training configuration (max_epochs=50, shuffle=True)