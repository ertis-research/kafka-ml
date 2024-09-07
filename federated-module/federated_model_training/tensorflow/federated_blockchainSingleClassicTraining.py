from web3 import Web3
import json

from federated_mainTraining import MainTraining

from utils import load_blockchain_federated_environment_vars

class BlockchainSingleClassicTraining(MainTraining):
    """Class for distributed models training
    
    Attributes:
        kml_cloud_bootstrap_server (str): Kafka bootstrap server for the KML Cloud
        data_bootstrap_server (str): Kafka bootstrap server for data
        federated_model_id (str): Federated model ID
        input_data_topic (str): Input data topic
        input_format (str): Input data format
        input_config (dict): Input data configuration
        validation_rate (float): Validation rate
        total_msg (int): Total number of messages

        eth_rpc_url (str): Ethereum RPC URL
        eth_contract_address (str): Ethereum contract address
        eth_contract_abi (str): Ethereum contract ABI
        eth_wallet_address (str): Ethereum wallet address
        eth_wallet_key (str): Ethereum wallet key
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

        self.eth_rpc_url, self.eth_contract_address, self.eth_contract_abi, self.eth_wallet_address, self.eth_wallet_key = load_blockchain_federated_environment_vars()
        
        self.web3_connection = Web3(Web3.HTTPProvider(self.eth_rpc_url))

        self.eth_wallet_address = self.web3_connection.toChecksumAddress(self.eth_wallet_address)
        self.eth_contract_address = self.web3_connection.toChecksumAddress(self.eth_contract_address)

        self.web3_connection.eth.defaultAccount = self.eth_wallet_address
        self.contract = self.web3_connection.eth.contract(address=self.eth_contract_address, abi=self.eth_contract_abi)    

    def get_current_round(self):
        """Gets the current round from the blockchain"""
        return self.contract.functions.getCurrentRound().call()
    
    def get_data(self, training_settings):
        """Gets the data from Kafka"""

        return super().get_kafka_dataset(training_settings)

    def load_model(self, message):
        """Downloads the model and loads it"""

        # TODO: Check hash at blockchain

        return super().load_model(message)
    
    def train(self, model, training_settings):
        """Trains the model"""
        
        return super().train_classic_model(model, training_settings)
    
    def save_metrics(self, model_trained):
        """Saves the metrics of the model"""
        
        return super().save_metrics(model_trained)
    
    def isTrainingActive(self):
        """Checks if the training is active"""
        
        return self.contract.functions.getTrainingStatus().call()
    
    def get_global_model(self, n_round):
        """Gets the global model from the blockchain"""

        model = {
            'topic': self.contract.functions.getGlobalModel(n_round).call(),
            'version': n_round,
            'training_settings': json.loads(self.contract.functions.getTrainingSettings().call()),
            'model_architecture': self.contract.functions.getModelArchitecture().call(),
            'model_compile_args': json.loads(self.contract.functions.getModelCompileArgs().call())
        }

        return model
    
    def send_updated_model(self, model, metrics, total_msg):
        """Sends the updated model to the blockchain"""
        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.sendClientContribution(model['topic'], json.dumps(metrics), total_msg).transact({'from': self.eth_wallet_address, 'nonce': nonce})
        self.web3_connection.eth.waitForTransactionReceipt(tx_hash)
        
        return tx_hash
