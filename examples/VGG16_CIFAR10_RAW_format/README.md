# VGG16 and CIFAR10

The following VGG16 TensorFlow deep learning model has been used in Kafka-ML for this example using the CIFAR10 dataset:

```
model =  tf.keras.applications.vgg16.VGG16( include_top=False, weights='imagenet', input_shape=(32,32,3),classes=10)

img_input = tf.keras.layers.Input( shape=( 32, 32, 3, ) )
x = model( img_input )
x = tf.keras.layers.Flatten()( x )
x = tf.keras.layers.Dense( 1024, activation='relu' )( x )
x = tf.keras.layers.Dense( 512, activation = "relu" )( x )
x = tf.keras.layers.Dense( 256, activation = "relu" )( x )
x = tf.keras.layers.Dense( 128, activation = "relu" )( x )
output = tf.keras.layers.Dense( 10, activation='softmax', name="cloud_output" )( x )


model = tf.keras.Model(inputs=img_input, outputs=output)

model.compile(
    optimizer= tf.keras.optimizers.SGD( lr = .001, momentum=.9 ),
    loss= tf.keras.losses.CategoricalCrossentropy(),
    metrics=['accuracy']
)
```
The batch_size used is 64, the training configuration (epochs=50, shuffle=True) and evaluation configuration (steps=50).