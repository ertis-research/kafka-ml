import logging

from mainTraining import *
from callbacks import *

from web3 import Web3
from blockchain_utils import create_federated_learning_smart_contract

from confluent_kafka import Producer
import re
import json


class BlockchainSingleFederatedTraining(MainTraining):
    """Class for single models federated training

    Attributes:
        boostrap_servers (str): list of boostrap server for the Kafka connection
        result_url (str): URL for downloading the untrained model
        result_id (str): Result ID of the model
        control_topic(str): Control topic
        deployment_id (int): deployment ID of the application
        batch (int): Batch size used for training
        kwargs_fit (:obj:json): JSON with the arguments used for training
        kwargs_val (:obj:json): JSON with the arguments used for validation
        model_logger_topic (str): Model logger topic
        federated_string_id (str): Federated string ID
        agg_rounds (int): Aggregation rounds
        data_restriction (str): Data restriction
        min_data (int): Minimum data
        agg_strategy (str): Aggregation strategy

        eth_rpc_url (str): Ethereum RPC URL
        eth_token_address (str): Ethereum token address
        eth_token_abi (str): Ethereum token ABI
        eth_chain_id (int): Ethereum chain ID
        eth_network_id (int): Ethereum network ID
        eth_wallet_address (str): Ethereum wallet address
        eth_wallet_key (str): Ethereum wallet key
        eth_blockscout_url (str): Ethereum blockscout URL
    """

    def __init__(self):
        """Loads the environment information"""

        super().__init__()

        self.distributed = False
        self.incremental = False

        (
            self.model_logger_topic,
            self.federated_string_id,
            self.agg_rounds,
            self.data_restriction,
            self.min_data,
            self.agg_strategy,
        ) = load_federated_environment_vars()

        logging.info(
            "Received federated environment information (model_logger_topic, federated_string_id, agg_rounds, data_restriction, min_data, agg_strategy) ([%s], [%s], [%d], [%s], [%d], [%s])",
            self.model_logger_topic,
            self.federated_string_id,
            self.agg_rounds,
            self.data_restriction,
            self.min_data,
            self.agg_strategy,
        )

        (
            self.eth_rpc_url,
            self.eth_token_address,
            self.eth_token_abi,
            self.eth_chain_id,
            self.eth_network_id,
            self.eth_wallet_address,
            self.eth_wallet_key,
            self.eth_blockscout_url,
        ) = load_blockchain_federated_environment_vars()

        logging.info(
            "Received blockchain federated environment information (eth_rpc_url, eth_token_address, eth_chain_id, eth_network_id, eth_wallet_address, eth_wallet_key, eth_blockscout_url) ([%s], [%s], [%d], [%d], [%s], [%s], [%s])",
            self.eth_rpc_url,
            self.eth_token_address,
            self.eth_chain_id,
            self.eth_network_id,
            self.eth_wallet_address,
            self.eth_wallet_key,
            self.eth_blockscout_url,
        )

        self.web3_connection = Web3(Web3.HTTPProvider(self.eth_rpc_url))

        self.eth_wallet_address = self.web3_connection.toChecksumAddress(
            self.eth_wallet_address
        )

        self.contract_address, self.contract_abi = (
            create_federated_learning_smart_contract(
                self.web3_connection,
                self.eth_wallet_address,
                self.eth_wallet_key,
                self.eth_blockscout_url,
            )
        )

        logging.info(
            "Created federated learning smart contract (contract_address: [%s]",
            self.contract_address
        )

        self.web3_connection.eth.defaultAccount = self.eth_wallet_address
        self.contract = self.web3_connection.eth.contract(
            address=self.contract_address, abi=self.contract_abi
        )


        self.token_contract = self.web3_connection.eth.contract(
            address=self.eth_token_address, abi=self.eth_token_abi
        )

    def __generate_and_send_data_standardization(
        self,
        model_logger_topic,
        federated_string_id,
        data_restriction,
        min_data,
        distributed,
        incremental,
    ):
        """Generates and sends the data standardization"""

        input_shape = str(self.model.input_shape)
        output_shape = str(self.model.output_shape)

        input_shape_sub = re.search(", (.+?)\)", input_shape)
        output_shape_sub = re.search(", (.+?)\)", output_shape)

        if input_shape_sub:
            input_shape = input_shape_sub.group(1)
            input_shape = input_shape.replace(",", "")
        if output_shape_sub:
            output_shape = output_shape_sub.group(1)
            output_shape = output_shape.replace(",", "")

        model_data_standard = {
            "model_format": {
                "input_shape": input_shape,
                "output_shape": output_shape,
            },
            "federated_params": {
                "federated_string_id": federated_string_id,
                "data_restriction": data_restriction,
                "min_data": min_data,
            },
            "framework": "tf",
            "distributed": distributed,
            "incremental": incremental,
            "blockchain": {
                "rpc_url": self.eth_rpc_url,
                "contract_address": self.contract_address,
                "contract_abi": self.contract_abi,
            },
        }

        logging.info("Model data standard: %s", model_data_standard)

        # Send model info to Kafka to notify that a new model is available
        prod = Producer({"bootstrap.servers": self.bootstrap_servers})

        # Send expected data standardization to Kafka
        prod.produce(model_logger_topic, json.dumps(model_data_standard))
        prod.flush()
        logging.info("Send the untrained model to Kafka Model Topic")

    def get_models(self):
        """Downloads the model and loads it"""

        super().get_single_model()

    def generate_and_send_data_standardization(self):
        """Generates and sends the data standardization"""

        self.__generate_and_send_data_standardization(
            self.model_logger_topic,
            self.federated_string_id,
            self.data_restriction,
            self.min_data,
            False,
            False,
        )

    def generate_federated_kafka_topics(self):
        """Generates the Kafka topics for the federated training"""

        super().generate_federated_kafka_topics()

    def parse_metrics(self, model_metrics):
        """Parse the metrics from the model"""

        return super().parse_metrics(model_metrics)

    def sendTempMetrics(self, train_metrics, val_metrics):
        """Send the metrics to the backend"""

        super().sendTempMetrics(train_metrics, val_metrics)

    def sendFinalMetrics(
        self,
        cf_generated,
        epoch_training_metrics,
        epoch_validation_metrics,
        test_metrics,
        dtime,
        cf_matrix,
    ):
        """Sends the metrics to the control topic"""

        self.stream_timeout = None

        return super().sendSingleMetrics(
            cf_generated,
            epoch_training_metrics,
            epoch_validation_metrics,
            test_metrics,
            dtime,
            cf_matrix,
        )

    # Blockchain functions
    def save_model_architecture(
        self, training_settings, model_architecture, model_compile_args
    ):
        """Saves the model architecture to the blockchain"""

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.saveTrainingSettings(
            training_settings, model_architecture, model_compile_args
        ).transact({"from": self.eth_wallet_address, "nonce": nonce})

        logging.info(
            "Saved model architecture into blockchain with training_settings [%s], model_architecture [%s], model_compile_args [%s], tx_hash [%s]",
            training_settings,
            model_architecture,
            model_compile_args,
            tx_hash.hex(),
        )

    def write_control_message_into_blockchain(self, control_message, n_round):
        """Writes the control message to the blockchain"""

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.saveGlobalModel(
            control_message, n_round
        ).transact({"from": self.eth_wallet_address, "nonce": nonce})

        logging.info(
            "Wrote control message into blockchain with control_message [%s], tx_hash [%s]",
            control_message,
            tx_hash.hex(),
        )

    def save_update_along_with_global_model(self, update_control_msg, global_control_msg):
        """Saves the update along with the global model"""

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.saveGlobalModelToUpdate(
            update_control_msg, global_control_msg
        ).transact({"from": self.eth_wallet_address, "nonce": nonce})

        logging.info(
            "Saved update along with global model into blockchain with update_control_msg [%s], global_control_msg [%s], tx_hash [%s]",
            update_control_msg,
            global_control_msg,
            tx_hash.hex(),
        )

    def elements_to_aggregate(self):
        """Gets the elements to aggregate"""

        elements_to_aggregate = self.contract.functions.getSize().call()

        return elements_to_aggregate

    def retrieve_last_model_from_queue(self):
        """Gets the last model from the blockchain queue"""

        last_model = self.contract.functions.getQueueFirstElement().call()

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.dequeueModel().transact(
            {"from": self.eth_wallet_address, "nonce": nonce}
        )

        logging.info(
            "Got last model from blockchain queue with last_model [%s], tx_hash [%s]",
            last_model,
            tx_hash.hex(),
        )

        last_model_metrics = json.loads(self.contract.functions.getModelMetrics(last_model).call())
        last_model_user = self.contract.functions.getModelAccount(last_model).call()
        last_model_data_size = self.contract.functions.getModelDataSize(last_model).call()

        return last_model, last_model_metrics, last_model_user, last_model_data_size
    
    def send_stopTraining(self):
        """Sends the stop training message to the blockchain"""

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.stopTraining().transact(
            {"from": self.eth_wallet_address, "nonce": nonce}
        )

        logging.info("Sent stop training message to blockchain with tx_hash [%s]", tx_hash.hex())

    def calculate_reward(self, rounds, control_msg, clients_contributions):
        """Calculate reward given to the user in that round"""
        BASE_REWARD = 100
        # Get metric from last round -1
        current_metrics = control_msg['metrics']        

        if rounds < 1:
            previous_loss = float('inf')
            current_loss = current_metrics['training']['loss'][-1] # First round has no previous loss, so we can use either loss or val_loss
        else:
            previous_metrics = json.loads(self.contract.functions.getMetricsByRound(rounds).call())
            if current_metrics['validation'].get('loss')[-1] is not None and previous_metrics['validation'].get('loss')[-1] is not None:
                try:
                    previous_loss = previous_metrics['validation']['loss'][-1]
                    current_loss = current_metrics['validation']['loss'][-1]
                except KeyError:
                    previous_loss = previous_metrics['training']['loss'][-1]
                    current_loss = current_metrics['training']['loss'][-1]
            else:
                current_loss = current_metrics['training']['loss'][-1]
                previous_loss = previous_metrics['training']['loss'][-1]



        # Calculate reward
        reward = 0

        if 0 <= current_loss/previous_loss <= 0.5:
            reward = 1
        elif 0.75 < current_loss/previous_loss <= 1:
            reward = 0.5
        elif 1 < current_loss/previous_loss <= 1.5:
            reward = 1/3
        else:
            reward = 0

        # Calculate reward based on data size
        data_size = 0
        
        for user in clients_contributions:
            data_size += clients_contributions[user]

        reward = reward * BASE_REWARD * control_msg["num_data"]/data_size

        logging.info(
            "Calculated reward [%s] for user [%s] with data size [%s] at round [%s]",
            reward,
            control_msg["account"],
            control_msg["num_data"],
            rounds,
        )

        nonce = self.web3_connection.eth.getTransactionCount(self.eth_wallet_address)
        tx_hash = self.contract.functions.setTokens(control_msg['topic'], Web3.toWei(int(reward), 'ether')).transact(
            {"from": self.eth_wallet_address, "nonce": nonce}
        )

        logging.info(
            "Set tokens into blockchain with reward [%s], tx_hash [%s]",
            reward,
            tx_hash.hex(),
        )

    def reward_participants(self):
        """Rewards all participants"""      
        participants = list(set(self.contract.functions.getParticipants().call()))

        rewards = {}

        for participant in participants:
            # get how much reward the participant has
            # TODO: Definir esta funcion en el Smart contract. 
            rewards[participant] = self.contract.functions.getReward(participant).call()

        # sum all rewards
        total_reward = sum(rewards.values())

        # check amount of tokens in wallet
        wallet_balance = self.token_contract.functions.balanceOf(self.eth_wallet_address).call()

        if wallet_balance < total_reward:
            logging.error("Not enough tokens in wallet to reward participants, weighted reward will be applied")
            total_reward = wallet_balance
            for participant in participants:
                rewards[participant] = rewards[participant] * total_reward / sum(rewards.values())
        
        # send the reward to the participant
        for participant, reward in rewards.items():
            nonce = self.web3_connection.eth.getTransactionCount(
                self.eth_wallet_address
            )
            tx_hash = self.token_contract.functions.transfer(participant, reward).transact(
                {"from": self.eth_wallet_address, "nonce": nonce}
            )

            logging.info("Sent reward [%s] to participant [%s], tx hash [%s]", reward, participant, tx_hash.hex())

            # Sleep to avoid spamming the blockchain and causing errors
            time.sleep(1)

        logging.info("Rewarded all participants")

