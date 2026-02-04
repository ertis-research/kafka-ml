import json

from django.conf import settings

from kubernetes import client


def is_blank(attribute):
    """Checks if the attribute is an empty string or None.
    Args:
        attribute (str): Attribute to check
    Returns:
        boolean: whether attribute is blank or not
    """
    return attribute is None or attribute == ""


def kubernetes_config(token=None, external_host=None):
    """Get Kubernetes configuration.
    You can provide a token and the external host IP
    to access a external Kubernetes cluster. If one
    of them is not provided the configuration returned
    will be for your local machine.
    Parameters:
        str: token
        str: external_host (e.g. "https://192.168.65.3:6443")
    Return:
        Kubernetes API client
    """
    aConfiguration = client.Configuration()
    if token is not None and external_host is not None:
        aConfiguration.host = external_host
        aConfiguration.verify_ssl = False
        aConfiguration.api_key = {"authorization": "Bearer " + token}

    api_client = client.ApiClient(aConfiguration)
    return api_client


def parse_kwargs_fit(kwargs_fit):
    """Converts kwargs_fit to a dictionary string
        kwargs_fit (str): Arguments for training.
        Example:
            epochs=5, steps_per_epoch=1000
    Returns:
        str: kwargs_fit formatted as string JSON
    """
    dic = {}
    if kwargs_fit is not None and kwargs_fit != "":
        kwargs_fit = kwargs_fit.replace(" ", "")
        for param in kwargs_fit.split(","):
            pair = param.split("=")
            dic[pair[0]] = eval(pair[1])

    return json.dumps(dic)


def delete_deploy(inference_id, token=None, external_host=None):
    """Delete a previous deployment.
    You can also provide an external host and its token
    to delete a deployment there. If one of them is not provided,
    this function will try to delete the deployment locally.

    Parameters:
        dict: inference_id ; Deployment ID
        str: token
        str: external_host (e.g. "https://192.168.65.3:6443")

    Return:
        Response of Kubernetes Cluster
    """
    api_client = kubernetes_config(token=token, external_host=external_host)
    api_instance = client.CoreV1Api(api_client)
    api_response = api_instance.delete_namespaced_replication_controller(
        name="model-inference-" + str(inference_id),
        namespace=settings.KUBE_NAMESPACE,
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )
    return api_response
