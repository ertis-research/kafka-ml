from channels.generic.websocket import WebsocketConsumer
from confluent_kafka import Consumer
from django.conf import settings
import json
import threading
import logging
import uuid

class KafkaThread (threading.Thread):
    """ Thread created when a new websocket clients connect. 
        Read data from a Kafka topic and sends the results to Websockets
        Args:
            topic (str): Kafka Topic to subscribe
            boostrap_servers (str): Kafka boostrap servers to subscribe
            ws (object): Websocket object
    """
    def __init__(self, topic, isClassification, boostrap_servers, ws):
        threading.Thread.__init__(self)
        self.topic = topic
        self.isClassification = isClassification
        self.boostrap_servers = boostrap_servers
        self.ws = ws
        self.running = True
        self.kafka_consumer  = Consumer({
            'bootstrap.servers': boostrap_servers, 
            'group.id':  uuid.uuid4(),
        })
    
    
    def __argmax(self, x):
        """Private function to calculate argmax"""
        return max(range(len(x)), key=lambda i: x[i])

    def run(self):
        """Creates an output consumer to receive the predictions"""
        self.kafka_consumer.subscribe([self.topic]) # Consumer subscribes to topic

        while self.running:
            try:
                msg = self.kafka_consumer.poll(timeout=10) # Waits for messages 10s
                if msg is None: # No message
                    continue
                if msg.error(): # Error Message
                    logging.error("Consumer error: {}".format(msg.error()))
                    continue
                
                if self.isClassification:
                    self.ws.send(text_data=str(self.__argmax(
                        json.loads(msg.value().decode())['values']
                    )))
                else:
                    self.ws.send(text_data=msg.value().decode())
            except Exception as e: 
                logging.error(str(e))
                pass
        self.kafka_consumer.close()
        
    def end(self):
        """Creates an output consumer to receive the predictions"""
        try:
            self.running = False
            logging.info("Client successfully stopped")
        except Exception as e: 
            logging.error(str(e))
            pass

class KafkaWSConsumer(WebsocketConsumer):
    """ 
        Class to manage websockets connections
    """
    def __init__(self):
        super().__init__()
        self.subscribers={}
   

    def websocket_connect(self, event):
        self.accept()
        logging.info("Client connected")

        
    def websocket_disconnect(self, close_code):
        if self.channel_name in self.subscribers:
            t  = self.subscribers[self.channel_name]
            if t is not None:
                t.end()
                del self.subscribers[self.channel_name]
                logging.info("Client successfully removed")

    def websocket_receive(self, event):
        jsonData = json.loads(event["text"])
        topic = jsonData['topic']
        isClassification = jsonData['classification']
        logging.info("Kafka consumer created for visualization in topic "+topic)
        thread= KafkaThread(topic, isClassification, settings.BOOTSTRAP_SERVERS, self)
        self.subscribers[self.channel_name] = thread
        thread.start()
        