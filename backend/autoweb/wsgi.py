"""
WSGI config for autoweb project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os
import json

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoweb.settings')

if os.environ.get('ENABLE_FEDML_BLOCKCHAIN') == '1':
    from autoweb import create_blockchain_token
    try:
        token_address, abi = create_blockchain_token.create_token(
            token_name=os.environ.get('FEDML_BLOCKCHAIN_TOKEN_NAME', "KafkaML Token"),
            token_symbol=os.environ.get('FEDML_BLOCKCHAIN_TOKEN_SYMBOL', "KML"),
            rpc_url=os.environ.get('FEDML_BLOCKCHAIN_RPC_URL', "http://localhost:8545"),
            chain_id=os.environ.get('FEDML_BLOCKCHAIN_CHAIN_ID', 1337),
            solc_version="0.8.6",
            wallet_address=os.environ.get('FEDML_BLOCKCHAIN_WALLET_ADDRESS', None),
            wallet_key=os.environ.get('FEDML_BLOCKCHAIN_WALLET_KEY', None)
        )

        os.environ['FEDML_BLOCKCHAIN_TOKEN_ADDRESS'] = token_address
        os.environ['FEDML_BLOCKCHAIN_ABI'] = json.dumps(abi)
        
    except Exception as e:
        print(f"Error creating blockchain token. Some parameters may be missing: {e}")
        raise e

application = get_wsgi_application()
