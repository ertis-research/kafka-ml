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

    def __init__(self, asynchronous, **params):
        self.asynchronous = asynchronous

    def configure(self, model):
        """Receives the global model before the first round, for strategies that need its structure"""

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

class FedOpt(Aggregator):
    """Base class of the adaptive federated optimizers (Reddi et al., 2021: FedAdagrad, FedYogi and FedAdam).

    The server treats the difference between the weighted average of the models of the clients and the global
    model as a pseudo-gradient and applies an adaptive optimizer to it, keeping its moments between rounds.
    Clients are not modified, they train locally and send their weights as in FedAvg. Weights that are not
    trainable (e.g. the statistics of batch normalization) are aggregated with FedAvg.

    Args:
        server_lr (float): learning rate of the server optimizer
        beta1 (float): decay of the first moment
        beta2 (float): decay of the second moment (not used by FedAdagrad)
        tau (float): degree of adaptivity, it avoids dividing by zero and initializes the second moment to tau^2
    """

    def __init__(self, asynchronous, server_lr=0.01, beta1=0.9, beta2=0.99, tau=1e-3, **params):
        super().__init__(asynchronous)
        self.server_lr, self.beta1, self.beta2, self.tau = server_lr, beta1, beta2, tau
        self.trainable = None
        self.m = None
        self.v = None

    def configure(self, model):
        trainable = {id(w) for w in model.trainable_weights}
        self.trainable = [id(w) in trainable for w in model.weights]

    def second_moment(self, v, delta):
        raise NotImplementedError

    def aggregate(self, global_weights, updates):
        if self.trainable is None:
            self.trainable = [True] * len(global_weights)
        if self.m is None:
            self.m = [np.zeros_like(g, dtype=np.float64) for g in global_weights]
            self.v = [np.full_like(g, self.tau ** 2, dtype=np.float64) for g in global_weights]

        coefficients = data_coefficients(updates)
        res = []
        for layer, g in enumerate(global_weights):
            average = sum(coef * update['weights'][layer].astype(np.float64) for coef, update in zip(coefficients, updates))
            if not self.trainable[layer]:
                res.append(average.astype(g.dtype))
                continue
            delta = average - g
            self.m[layer] = self.beta1 * self.m[layer] + (1 - self.beta1) * delta
            self.v[layer] = self.second_moment(self.v[layer], delta)
            res.append((g + self.server_lr * self.m[layer] / (np.sqrt(self.v[layer]) + self.tau)).astype(g.dtype))
        return res

class FedAdagrad(FedOpt):
    """FedAdagrad: v = v + delta^2"""

    def second_moment(self, v, delta):
        return v + delta ** 2

class FedYogi(FedOpt):
    """FedYogi: v = v - (1 - beta2) * delta^2 * sign(v - delta^2)"""

    def second_moment(self, v, delta):
        return v - (1 - self.beta2) * delta ** 2 * np.sign(v - delta ** 2)

class FedAdam(FedOpt):
    """FedAdam: v = beta2 * v + (1 - beta2) * delta^2"""

    def second_moment(self, v, delta):
        return self.beta2 * v + (1 - self.beta2) * delta ** 2

AGGREGATORS = {
    'FedAvg': FedAvg,
    'FedAdagrad': FedAdagrad,
    'FedAdam': FedAdam,
    'FedYogi': FedYogi,
}
"""Implemented aggregation strategies"""

ADAPTIVE_AGGREGATORS = ('FedAdagrad', 'FedAdam', 'FedYogi')
"""Strategies whose server optimizer needs several updates per round, so they cannot be asynchronous"""

PENDING_AGGREGATORS = ()
"""Aggregation strategies offered by the backend that are not implemented yet"""

def get_aggregator(strategy, asynchronous, **params):
    """Returns the aggregator of the strategy received, params are the hyperparameters of the strategy"""

    if strategy in PENDING_AGGREGATORS:
        raise NotImplementedError('Aggregation strategy {} is not implemented yet'.format(strategy))
    if strategy not in AGGREGATORS:
        raise ValueError('Unknown aggregation strategy {}'.format(strategy))
    if asynchronous and strategy in ADAPTIVE_AGGREGATORS:
        raise ValueError('Aggregation strategy {} requires more than one client per round'.format(strategy))
    return AGGREGATORS[strategy](asynchronous, **params)

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
