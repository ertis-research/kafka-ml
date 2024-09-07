from web3 import Web3
from solcx import compile_standard, install_solc, set_solc_version
import json
import os

def create_and_compile_contract(token_name: str, token_symbol: str, solc_version: str) -> dict:
    # print actual working directory
    print(os.getcwd())

    # create a base path variable at cwd + autoweb + contracts + token + ERC20
    base_path = os.path.join(os.getcwd(), "autoweb", "contracts", "token", "ERC20")

    
    token_contract = f"""
    // SPDX-License-Identifier: MIT
    pragma solidity ^{solc_version};
    import "ERC20.sol";
    contract Token is ERC20 {{
        constructor() ERC20("{token_name}", "{token_symbol}") {{
            _mint(msg.sender, 1e25);
        }}
    }}"""
    
    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {"Token.sol": {"content": token_contract}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "metadata", "evm.bytecode", "evm.bytecode.sourceMap"]
                    }
                }
            },
        },
        solc_version=solc_version,
        base_path=base_path,
        allow_paths=[base_path]
    )

    return compiled_sol

def create_transaction(w3: Web3, chain_id: int, compiled_sol: dict, wallet_address: str):

    # get bytecode
    bytecode = compiled_sol["contracts"]["Token.sol"]["Token"]["evm"]["bytecode"]["object"]
    # get abi
    abi = json.loads(compiled_sol["contracts"]["Token.sol"]["Token"]["metadata"])["output"]["abi"]

    # create a transaction
    checksum_address = w3.toChecksumAddress(wallet_address)
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.getTransactionCount(checksum_address)
    tx = contract.constructor().buildTransaction(
        {
        "gasPrice": w3.eth.gas_price,
        "from": checksum_address,
        "nonce": nonce,
        "chainId": chain_id,
        }
    )

    return tx, abi

def sign_and_send_transaction(w3: Web3, tx: dict, wallet_key: str):
    # Sign the transaction
    sign_transaction = w3.eth.account.signTransaction(tx, private_key=wallet_key)
    print("Deploying Contract!")
    # Send the transaction
    transaction_hash = w3.eth.sendRawTransaction(sign_transaction.rawTransaction)

    # Wait for the transaction to be mined, and get the transaction receipt
    print("Waiting for transaction to finish...")
    transaction_receipt = w3.eth.waitForTransactionReceipt(transaction_hash)
    print(f"Done! Contract deployed to {transaction_receipt.contractAddress}")

    return transaction_receipt.contractAddress


def create_token(token_name: str, token_symbol: str, rpc_url: str, chain_id: int, solc_version: str, wallet_address: str, wallet_key: str):
    install_solc(solc_version)
    set_solc_version(solc_version)

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    compiled_sol = create_and_compile_contract(token_name, token_symbol, solc_version)    
    tx, abi = create_transaction(w3, chain_id, compiled_sol, wallet_address)


    token_address = sign_and_send_transaction(w3, tx, wallet_key)

    return token_address, abi

