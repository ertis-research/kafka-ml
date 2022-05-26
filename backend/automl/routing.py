# chat/routing.py
from django.urls import re_path

from . import websockets

websocket_urlpatterns = [
    re_path(r'ws/$', websockets.KafkaWSConsumer.as_asgi()),
]
