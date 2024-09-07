__author__ = 'Antonio J. Chaves'

import os
import traceback

from decoders import *
from utils import *


from classic_federated_training import classicFederatedTraining
from blockchain_federated_training import blockchainFederatedTraining


from federated_singleClassicTraining import SingleClassicTraining
from federated_singleIncrementalTraining import SingleIncrementalTraining
from federated_distributedClassicTraining import DistributedClassicTraining
from federated_distributedIncrementalTraining import DistributedIncrementalTraining
from federated_blockchainSingleClassicTraining import BlockchainSingleClassicTraining

if __name__ == '__main__':
  try:
    configure_logging()
    """Configures the logging"""

    select_gpu()
    """Configures the GPU"""

    case = int(os.environ.get('CASE')) if os.environ.get('CASE') else 1

    if case == FEDERATED_NOT_DISTRIBUTED_NOT_INCREMENTAL:
      classicFederatedTraining(SingleClassicTraining())
    elif case == FEDERATED_NOT_DISTRIBUTED_INCREMENTAL:
      classicFederatedTraining(SingleIncrementalTraining())
    elif case == FEDERATED_DISTRIBUTED_NOT_INCREMENTAL:
      classicFederatedTraining(DistributedClassicTraining())
    elif case == FEDERATED_DISTRIBUTED_INCREMENTAL:
      classicFederatedTraining(DistributedIncrementalTraining())
    elif case == BLOCKCHAIN_FEDERATED_NOT_DISTRIBUTED_NOT_INCREMENTAL:
      blockchainFederatedTraining(BlockchainSingleClassicTraining())
    else:
      raise ValueError(case)

  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))