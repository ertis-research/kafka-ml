# Kustomize for Kafka-ML

This folder contains multiple Kustomize files to ease the deployment on
Kubernetes. Notably the following versions are available:

| Version      | Resource URL                                              |
| ------------ | --------------------------------------------------------- |
| `master`     | `github.com/ertis-research/kafka-ml/kustomize/master`     |
| `master-gpu` | `github.com/ertis-research/kafka-ml/kustomize/master-gpu` |
| `local`      | `github.com/ertis-research/kafka-ml/kustomize/local`      |

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
