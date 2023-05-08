# Kustomize for Kafka-ML

This folder contains multiple Kustomize files to ease the deployment on
Kubernetes. Notably the following versions are available:

| Version      | Resource URL                                              |
| ------------ | --------------------------------------------------------- |
| `master`     | `github.com/ertis-research/kafka-ml/kustomize/master`     |
| `master-gpu` | `github.com/ertis-research/kafka-ml/kustomize/master-gpu` |
| `local`      | `github.com/ertis-research/kafka-ml/kustomize/local`      |

These versions should work with any Kubernetes compatible cluster, such as K8s
and K3s.

## Installation

1. Create a `kustomize.yaml` file with the following contents:

```yaml
resources:
  # Choose your kustomize version
  - github.com/ertis-research/kafka-ml/kustomize/master

# Namespace where Kafka-ML will be deployed
namespace: kafkaml

configMapGenerator:
  - name: kafkaml-configmap
    behavior: merge
    literals:
      # Comma separated list of Kafka brokers
      - brokers=kafka1,kafka2,kafka3
```

2. Deploy using the following command

```sh
# Create the namespace first if it doesn't exists
kubectl create namespace kafkaml
kubectl apply -k .
```

## Configuration options

You can modify the `kafkaml-configmap` resource to customize the installation.
The available keys are:

| Key                          | Description                                      | Default value               |
| ---------------------------- | ------------------------------------------------ | --------------------------- |
| `frontend.url`               | Frontend's URL                                   | http://localhost            |
| `backend.url`                | Backend's URL                                    | http://backend:8000         |
| `backend.address`            | Backend's address and port                       | backend:8000                |
| `backend.allowedhosts`       | Configures the `Allowed-Hosts` header of backend | 127.0.0.1,localhost,backend |
| `tfexecutor.url`             | TensorFlow executor's URL                        | http://tfexecutor:8001/     |
| `pthexecutor.url`            | PyTorch executor's URL                           | http://pthexecutor:8002/    |
| `tensorflow.training.image`  | Container image used for TensorFlow training     | \*                          |
| `tensorflow.inference.image` | Container image used for TensorFlow inference    | \*                          |
| `pytorch.training.image`     | Container image used for PyTorch training        | \*                          |
| `pytorch.inference.image`    | Container image used for PyTorch inference       | \*                          |
| `brokers`                    | Comma separated list of Kafka brokers            | -                           |
| `debug`                      | Enable debug mode. Possible values: `[0,1]`      | -                           |

> \* value depends on the kustomize version used. See
> [Kustomize for Kafka-ML](#kustomize-for-kafka-ml)
