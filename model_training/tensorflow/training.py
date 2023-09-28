__author__ = 'Cristian Martin Fdz'

import os
import traceback

from decoders import *
from utils import *

from singleClassicTraining import SingleClassicTraining
from distributedClassicTraining import DistributedClassicTraining
from singleIncrementalTraining import SingleIncrementalTraining
from distributedIncrementalTraining import DistributedIncrementalTraining
from singleFederatedTraining import SingleFederatedTraining
from singleFederatedIncrementalTraining import SingleFederatedIncrementalTraining
from distributedFederatedTraining import DistributedFederatedTraining
from distributedFederatedIncrementalTraining import DistributedFederatedIncrementalTraining

from edgeBasedTraining import EdgeBasedTraining
from cloudBasedTraining import CloudBasedTraining

if __name__ == '__main__':
  try:
    configure_logging()
    """Configures the logging"""

    select_gpu()
    """Configures the GPU"""

    case = int(os.environ.get('CASE'))
    """Gets type of training"""
     
    if case == NOT_DISTRIBUTED_NOT_INCREMENTAL:
      CloudBasedTraining(SingleClassicTraining())
    elif case == NOT_DISTRIBUTED_INCREMENTAL:
      CloudBasedTraining(SingleIncrementalTraining())
    elif case == DISTRIBUTED_NOT_INCREMENTAL:
      CloudBasedTraining(DistributedClassicTraining())
    elif case == DISTRIBUTED_INCREMENTAL:
      CloudBasedTraining(DistributedIncrementalTraining())
    elif case == FEDERATED_LEARNING:
      EdgeBasedTraining(SingleFederatedTraining())
    elif case == FEDERATED_INCREMENTAL_LEARNING:
      EdgeBasedTraining(SingleFederatedIncrementalTraining())
    elif case == FEDERATED_DISTRIBUTED_LEARNING:
      EdgeBasedTraining(DistributedFederatedTraining())
    elif case == FEDERATED_DISTRIBUTED_INCREMENTAL_LEARNING:
      EdgeBasedTraining(DistributedFederatedIncrementalTraining())
    else:
      raise ValueError(case)
    """Get the training class"""

  except Exception as e:
      traceback.print_exc()
      logging.error("Error in main [%s]. Service will be restarted.", str(e))