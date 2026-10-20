import numpy as np

class Aggregator(object):
    """Base class for the aggregation strategies of the federated server.

    Each update received from a federated device is a dict with the keys 'weights' (list of ndarrays),
    'num_data' (number of samples used for training), 'metrics' (training and validation metrics),
    'version' (model version returned by the device) and 'client' (device identifier).
    Strategies may keep state between rounds (e.g. server-side optimizers).

    Args:
        asynchronous (bool): True if the global model is aggregated with every update as soon as it arrives
    """

    def __init__(self, asynchronous):
        self.asynchronous = asynchronous

    def aggregate(self, global_weights, updates):
        """Returns the new global weights given the current global weights and the updates of the round"""

        raise NotImplementedError

class FedAvg(Aggregator):
    """Federated Averaging (McMahan et al., 2017).

    Synchronous: the new global model is the average of the received models weighted by their number of samples.
    Asynchronous: the received model is mixed with the global one, w = (1 - alpha) * w + alpha * w_client
    (FedAsync, Xie et al., 2019), as averaging a single update would just replace the global model.
    """

    ASYNC_MIXING = 0.5

    def aggregate(self, global_weights, updates):
        if self.asynchronous:
            client_weights = updates[0]['weights']
            return [((1 - self.ASYNC_MIXING) * g + self.ASYNC_MIXING * c).astype(g.dtype)
                    for g, c in zip(global_weights, client_weights)]

        coefficients = data_coefficients(updates)
        return [sum(coef * update['weights'][layer] for coef, update in zip(coefficients, updates)).astype(g.dtype)
                for layer, g in enumerate(global_weights)]

AGGREGATORS = {
    'FedAvg': FedAvg,
}
"""Implemented aggregation strategies"""

PENDING_AGGREGATORS = ('FedOpt', 'FedAdagrad', 'FedAdam', 'FedYogi')
"""Aggregation strategies offered by the backend that are not implemented yet"""

def get_aggregator(strategy, asynchronous):
    """Returns the aggregator of the strategy received"""

    if strategy in PENDING_AGGREGATORS:
        raise NotImplementedError('Aggregation strategy {} is not implemented yet'.format(strategy))
    if strategy not in AGGREGATORS:
        raise ValueError('Unknown aggregation strategy {}'.format(strategy))
    return AGGREGATORS[strategy](asynchronous)

def data_coefficients(updates):
    """Returns the weight of each update proportional to its number of samples (uniform if unknown)"""

    num_data = [max(int(update.get('num_data') or 0), 0) for update in updates]
    total = sum(num_data)
    if total == 0:
        return [1.0 / len(updates)] * len(updates)
    return [n / total for n in num_data]

def check_weights(global_weights, client_weights):
    """Checks that the weights received from a device match the global model"""

    if len(global_weights) != len(client_weights):
        raise ValueError('Received {} weight tensors, expected {}'.format(len(client_weights), len(global_weights)))
    for idx, (g, c) in enumerate(zip(global_weights, client_weights)):
        if np.shape(g) != np.shape(c):
            raise ValueError('Weight tensor {} has shape {}, expected {}'.format(idx, np.shape(c), np.shape(g)))

def aggregate_metrics(updates):
    """Combines the metrics of the updates of a round into a single entry weighted by their number of samples"""

    if len(updates) == 1:
        return updates[0]['metrics']

    coefficients = data_coefficients(updates)
    res = {}
    for split in ('training', 'validation'):
        res[split] = {}
        for key in updates[0]['metrics'].get(split, {}):
            if all(key in update['metrics'].get(split, {}) for update in updates):
                res[split][key] = [float(sum(coef * update['metrics'][split][key][-1] for coef, update in zip(coefficients, updates)))]
    return res
