import requests
import json
import logging
import urllib.parse
from web3 import Web3
from solcx import compile_standard, install_solc, set_solc_version

SOLC_VERSION = "0.8.6"


def create_federated_learning_smart_contract(
    eth_web3_connection: Web3,
    eth_wallet_address,
    eth_wallet_key,
    eth_blockscout_url,
):
    """Creates the federated learning smart contract

    Args:
        eth_web3_connection (Web3): Web3 connection
        eth_wallet_address (str): Ethereum wallet address
        eth_wallet_key (str): Ethereum wallet key
        eth_blockscout_url (str): Ethereum blockscout URL
    return:
        str: Smart contract address
        str: Smart contract ABI
    """

    # Install the solidity compiler
    install_solc(SOLC_VERSION)

    # Set the solidity compiler version
    set_solc_version(SOLC_VERSION)

    # compile the contract from contracts/FederatedLearning.sol

    federated_learning_file = open("contracts/FederatedLearning.sol", "r").read()

    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {"FederatedLearning.sol": {"content": federated_learning_file}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": [
                            "abi",
                            "metadata",
                            "evm.bytecode",
                            "evm.bytecode.sourceMap",
                        ]  # output needed to interact with and deploy contract
                    }
                }
            },
        },
        solc_version=SOLC_VERSION,
    )

    # get bytecode
    bytecode = compiled_sol["contracts"]["FederatedLearning.sol"]["FederatedLearning"][
        "evm"
    ]["bytecode"]["object"]
    abi = json.loads(
        compiled_sol["contracts"]["FederatedLearning.sol"]["FederatedLearning"][
            "metadata"
        ]
    )["output"]["abi"]

    # Connect to the blockchain
    contract = eth_web3_connection.eth.contract(abi=abi, bytecode=bytecode)

    nonce = eth_web3_connection.eth.getTransactionCount(eth_wallet_address)

    # build transaction
    transaction = contract.constructor().buildTransaction(
        {
            "gasPrice": eth_web3_connection.eth.gas_price,
            "from": eth_web3_connection.toChecksumAddress(eth_wallet_address),
            "nonce": nonce,
        }
    )

    # Sign the transaction
    sign_transaction = eth_web3_connection.eth.account.signTransaction(
        transaction, private_key=eth_wallet_key
    )
    logging.info("Deploying Contract!")

    # Send the transaction
    transaction_hash = eth_web3_connection.eth.sendRawTransaction(
        sign_transaction.rawTransaction
    )

    # Wait for the transaction to be mined, and get the transaction receipt
    logging.info("Waiting for transaction to finish...")
    transaction_receipt = eth_web3_connection.eth.waitForTransactionReceipt(
        transaction_hash
    )
    logging.info(f"Done! Contract deployed to {transaction_receipt.contractAddress}")

    if eth_blockscout_url:
        logging.info("Trying to verify contract on blockscout...")
        try:
            contract_verify_json = {
                "addressHash": transaction_receipt.contractAddress,
                "compilerVersion": json.loads(
                    compiled_sol["contracts"]["FederatedLearning.sol"][
                        "FederatedLearning"
                    ]["metadata"]
                )["compiler"]["version"],
                "name": "FederatedLearning",
                "optimization": False,
                "contractSourceCode": federated_learning_file,
            }

            eth_blockscout_url = urllib.parse.urljoin(eth_blockscout_url, "/api?module=contract&action=verify")

            response = requests.post(eth_blockscout_url,json=contract_verify_json, timeout=30)

            # TODO: Check pq no se valida (la response da 500 cuando va muy rapido, pero si voy poco a poco va bien??)

            if response.status_code == 200 and response.json()["message"] == "OK":
                logging.info(f"Contract verified on provided Blockscout: {response.json()}")

        except Exception as e:
            logging.error(f"Failed to verify contract on provided Blockscout: {e}")

    return transaction_receipt.contractAddress, abi
