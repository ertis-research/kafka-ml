# Kafka-ML Federated Module

Federated learning is a privacy-preserving machine learning approach that enables
collaborative model training across multiple decentralized devices without the
need to transfer sensitive data to a central location. In federated learning,
instead of sending raw data to a central server for training, local devices
perform the training on their own data and only share model updates or gradients
with the central server. These updates are then aggregated to create an improved
global model, which is sent back to the devices for further training. 
This distributed learning approach allows for the benefits of collective intelligence
while ensuring data privacy and reducing the need for large-scale data transfers.
Federated learning has gained popularity in scenarios where data is sensitive or
resides in diverse locations, such as mobile devices, healthcare systems, and IoT networks.

Currently, the only framework that supports federated learning is TensorFlow.
In this case, the usage example will be the same as the one presented for the
single models, only the configuration deployment form will change and will now
contain more fields.


## Table of Contents

- [Changelog](#changelog)
- [Deploy Kafka-ML Federated Module in a fast way](#Deploy-Kafka-ML-Federated-Module-in-a-fast-way)
  - [Requirements](#Requirements)
  - [Steps to run Kafka-ML Federated Module](#Steps-to-run-Kafka-ML-Federated-Module)
- [Installation and development](#Installation-and-development)
  - [Requirements to build locally](#Requirements-to-build-locally)
  - [Steps to build Kafka-ML Federated Module](#Steps-to-build-Kafka-ML-Federated-Module)
  - [GPU configuration](#GPU-configuration)
- [License](#license)

## Changelog

- [07/07/2023] Added federated training support (currently only for Tensorflow/Keras models).

## Deploy Kafka-ML Federated Module in a fast way

### Requirements

- [Docker](https://www.docker.com/)
- [kubernetes>=v1.15.5](https://kubernetes.io/)

### Steps to run Kafka-ML Federated Module

For a basic local installation, we recommend using Docker Desktop with
Kubernetes enabled. Please follow the installation guide on
[Docker's website](https://docs.docker.com/desktop/). To enable Kubernetes,
refer to
[Enable Kubernetes](https://docs.docker.com/desktop/kubernetes/#enable-kubernetes)

Once Kubernetes is running, open a terminal and run the following command:

```sh
# Uncomment only if you are running Kafka-ML Federated Module on Apple Silicon
# export DOCKER_DEFAULT_PLATFORM=linux/amd64
kubectl apply -k "github.com/ertis-research/kafka-ml/federated-module/kustomize/local?ref=v1.1"
```

This will install all the required components for Kafka-ML Federated Module,
plus Apache Kafka on the namespace `kafkaml`. 

For a more advanced installation on Kubernetes, please refer to the
[kustomization guide](kustomize/README.md)

## Usage

To follow this tutorial, please deploy Kafka-ML Federated Module as indicated in
[Deploy Kafka-ML Federated Module in a fast way](#Deploy-Kafka-ML-Federated-Module-in-a-fast-way) or
[Installation and development](#Installation-and-development).

## Installation and development

### Requirements to build locally

- [Python supported by Tensorflow 3.5–3.7 and PyTorch 1.10](https://www.python.org/)
- [Node.js](https://nodejs.org/)
- [Docker](https://www.docker.com/)
- [kubernetes>=v1.15.5](https://kubernetes.io/)

### Steps to build Kafka-ML Federated Module

In this repository you can find files to build Kafka-ML Federated Module in case you want to
contribute.

By default, Kafka-ML Federated Module will be built using CPU-only images. If you
desire to build Kafka-ML Federated Module with images enabled for GPU acceleration, the
`Dockerfile` and `requirements.txt` files of `federated_model_training` module
must be modified as indicated in those files.

In case you want to build Kafka-ML Federated Module step-by-step, then follow the following
steps:

1. You may need to deploy a local register to upload your Docker images. You can
   deploy it in the port 5000:

   ```bash
   docker run -d -p 5000:5000 --restart=always --name registry registry:2
   ```

2. Build the backend and push the image into the local register:

   ```bash
   cd backend
   docker build --tag localhost:5000/federated_backend .
   docker push localhost:5000/federated_backend
   ```

3. Build the model_training components and push the images into the local
   register:

   ```bash
   cd federated_model_training/tensorflow
   docker build --tag localhost:5000/federated_tensorflow_model_training .
   docker push localhost:5000/federated_tensorflow_model_training
   ```

4. Build the federated_model_control_logger component and push the image into the local
   register:

   ```bash
   cd federated_model_control_logger
   docker build --tag localhost:5000/federated_model_control_logger .
   docker push localhost:5000/federated_model_control_logger
   ```

5. Build the federated_data_control_logger component and push the image into the local
   register:

   ```bash
   cd federated_data_control_logger
   docker build --tag localhost:5000/federated_data_control_logger .
   docker push localhost:5000/federated_data_control_logger
   ```

Once built the images, you can deploy the system components in Kubernetes modifying
the `image` field of the `deployment.yaml` files in the `kustomize/local` folder.

### GPU configuration

The following steps are required in order to use GPU acceleration in Kafka-ML Federated Module
and Kubernetes. These steps are required to be performed in all the Kubernetes
nodes.

1. GPU Driver installation

```bash
# SSH into the worker machine with GPU
$ ssh USERNAME@EXTERNAL_IP

# Verify ubuntu driver
$ sudo apt install ubuntu-drivers-common
$ ubuntu-drivers devices

# Install the recommended driver
$ sudo ubuntu-drivers autoinstall

# Reboot the machine
$ sudo reboot

# After the reboot, test if the driver is installed correctly
$ nvidia-smi
```

2. Nvidia Docker installation

```bash
# SSH into the worker machine with GPU
$ ssh USERNAME@EXTERNAL_IP

# Add the package repositories
$ distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
$ curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
$ curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

$ sudo apt-get update && sudo apt-get install -y nvidia-docker2
$ sudo systemctl restart docker
```

3. Modify the following file

```bash
# SSH into the worker machine with GPU
$ ssh USERNAME@EXTERNAL_IP
$ sudo tee /etc/docker/daemon.json <<EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF
$ sudo pkill -SIGHUP docker
$ sudo reboot
```

4. Kubernetes GPU Sharing extension installation

```bash
# From your local machine that has access to the Kubernetes API
$ curl -O https://raw.githubusercontent.com/AliyunContainerService/gpushare-scheduler-extender/master/config/gpushare-schd-extender.yaml
$ kubectl create -f gpushare-schd-extender.yaml

$ wget https://raw.githubusercontent.com/AliyunContainerService/gpushare-device-plugin/master/device-plugin-rbac.yaml
$ kubectl create -f device-plugin-rbac.yaml

$ wget https://raw.githubusercontent.com/AliyunContainerService/gpushare-device-plugin/master/device-plugin-ds.yaml
# update the local file so the first line is 'apiVersion: apps/v1'
$ kubectl create -f device-plugin-ds.yaml

# From your local machine that has access to the Kubernetes API
$ kubectl label node worker-gpu-0 gpushare=true
```

Thanks to Sven Degroote from ML6team for the GPU and Kubernetes setup
[documentation](https://blog.ml6.eu/a-guide-to-gpu-sharing-on-top-of-kubernetes-6097935ababf).

## License

MIT
