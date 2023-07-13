import logging
from kafka import KafkaConsumer, TopicPartition
import pickle
import tensorflow as tf

class KafkaModelEngine():
      def __init__(self, bootstrap_servers, group_id):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
      
      def getModel(self, controlMessage):
        model = tf.keras.models.model_from_json(controlMessage['model_architecture'])
        weights = self.__getModelWeights__(controlMessage) 
        
        model.set_weights(weights)

        compileParams = self.__deserialize_compile_args__(controlMessage['model_compile_args'])

        model.compile(**compileParams) # TODO: Checkear metricas, bypass con string actualmente.
        
        return model 

      def __deserialize_compile_args__(self, compile_args):
        res = {}
        for k in compile_args.keys():
            try:
                if k == 'optimizer':
                    res[k] = tf.keras.optimizers.deserialize(compile_args[k])
                elif k == 'loss':
                    res[k] = tf.keras.losses.deserialize(compile_args[k])
                elif k in ['metrics', 'weighted_metrics']:
                    # compile_args[k] = [tf.keras.metrics.deserialize(metric) for metric in compile_args[k]] # TODO: Comentado hasta resolver tema Shapes Error
                    res[k] = compile_args[k]
                else:
                    res[k] = compile_args[k]
            except:
                res[k] = compile_args[k] # If none in one of above, return None.
        return res
      

      def __getModelWeights__(self, controlMessage):
        data = []
        for kafkaControl in self.__splitPartitionsIntoControlMsgs__(controlMessage):
            consumer, end_offset = self.__createconsumer__(kafkaControl)
            for message in consumer:
                print(message.offset)
                decoded_data = self.__decodedata__(message)
                data.insert(decoded_data[1], decoded_data[0])
                if message.offset >= end_offset-1:
                    consumer.unsubscribe()
                    logging.info("Finished reading model weights from Kafka")
                    break

        print("Data received: ", len(data))
            
        return data        

      def __splitPartitionsIntoControlMsgs__(self, controlMessage):
        res = []
        partitions = controlMessage['topic'].split(',')
        for topic in partitions:
            auxControlMessage = controlMessage.copy()
            auxControlMessage['topic'] = topic
            res.append(controlMessage)
            
        return res

      def __createconsumer__(self, controlMessage):
        topic = controlMessage['topic'].split(":")
        print(topic)
        consumer = KafkaConsumer(bootstrap_servers = self.bootstrap_servers,
                        enable_auto_commit = False,
                        group_id = self.group_id,
                        max_poll_records = 2**31-1,
                        max_partition_fetch_bytes = 2**31-1
                        )
        # consumer.poll()
        consumer.assign([TopicPartition(topic[0], int(topic[1]))])
        tp, start_offset, end_offset = TopicPartition(topic[0], int(topic[1])), int(topic[2]), int(topic[3])
        
        consumer.seek(tp, start_offset)

        return consumer, end_offset

    
      def __decodedata__(self, input):
        value = pickle.loads(input.value)
                                                    
        label = int.from_bytes(input.key, byteorder='big', signed=False)

        return (value, label)