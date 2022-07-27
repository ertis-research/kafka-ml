#!/bin/bash

NAMESPACE="kafkaml"
LOCAL_BUILD=false

echo Selected namespace \"$NAMESPACE\" and local build is \"$LOCAL_BUILD\"
echo Hi "$USER", what do you want me to do?
echo 0 - Fresh install of Kafka-ML
echo 1 - Rebuild and deploy Backend Module
echo 2 - Rebuild and deploy Frontend Module
echo 3 - Rebuild and deploy TensorFlow Executor
echo 4 - Rebuild and deploy PyTorch Executor
echo 5 - Rebuild and deploy Model Training
echo 6 - Rebuild and deploy Model Inference
echo 7 - Rebuild and deploy Kafka
echo 8 - Rebuild and deploy Kafka Control Logger
echo 9 - Rebuild and deploy ZooKeeper

read input

if [ $input -eq 0 ]
then
    kubectl create namespace $NAMESPACE
    kubectl apply -f permissions-fix.yaml

    kubectl delete service backend -n $NAMESPACE
    kubectl delete service frontend -n $NAMESPACE
    kubectl delete service kafka-cluster -n $NAMESPACE
    kubectl delete service pthexecutor -n $NAMESPACE
    kubectl delete service tfexecutor -n $NAMESPACE
    kubectl delete service zookeeper -n $NAMESPACE

    kubectl apply -f backend-service.yaml -n $NAMESPACE
    kubectl apply -f zookeeper-service.yaml -n $NAMESPACE
    kubectl apply -f kafka-service.yaml -n $NAMESPACE
    kubectl apply -f frontend-service.yaml -n $NAMESPACE
    kubectl apply -f tf-executor-service.yaml -n $NAMESPACE
    kubectl apply -f pth-executor-service.yaml -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        docker run -d -p 5000:5000 --restart=always --name registry registry:2 & # It will throw an error if you already have a registry
    fi
fi

if [ $input -eq 0 ] || [ $input -eq 9 ]
then
    # Zookeeper
    kubectl delete pod zookeeper -n $NAMESPACE
    kubectl apply -f zookeeper-pod.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 7 ]
then
    # Kafka
    kubectl delete pod kafka-pod -n $NAMESPACE
    kubectl apply -f kafka-pod.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 1 ]
then
    # Backend
    kubectl get jobs --no-headers=true -n $NAMESPACE | awk "/model-training/{print $1}" | xargs kubectl delete jobs -n $NAMESPACE

    kubectl delete deploy backend -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        cd backend
        docker build --tag localhost:5000/backend .
        docker push localhost:5000/backend 
        cd ..
    fi

    kubectl apply -f backend-deployment.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 2 ]
then
    # Frontend (Heavy Load!)
    kubectl delete deploy frontend -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        cd frontend
        sudo npm install
        sudo npm i -g @angular/cli
        sudo ng build -c production
        docker build --tag localhost:5000/frontend .
        docker push localhost:5000/frontend
        cd ..
    fi

    kubectl apply -f frontend-deployment.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 3 ]
then
    # TensorFlow Executor 
    kubectl delete deploy tfexecutor -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        cd mlcode_executor/tfexecutor
        docker build --tag localhost:5000/tfexecutor .
        docker push localhost:5000/tfexecutor 
        cd ../..
    fi
    
    kubectl apply -f tf-executor-deployment.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 4 ]
then
    # PyTorch Executor 
    kubectl delete deploy pthexecutor -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        cd mlcode_executor/pthexecutor
        docker build --tag localhost:5000/pthexecutor .
        docker push localhost:5000/pthexecutor 
        cd ../..
    fi
    
    kubectl apply -f pth-executor-deployment.yaml -n $NAMESPACE
fi

if [ $input -eq 0 ] || [ $input -eq 5 ]
then
    # Model training module
    if [ $LOCAL_BUILD == true ]
    then
        cd model_training/tensorflow 
        docker build --tag localhost:5000/tensorflow_model_training .
        docker push localhost:5000/tensorflow_model_training 
        cd ../pytorch
        docker build --tag localhost:5000/pytorch_model_training .
        docker push localhost:5000/pytorch_model_training
        cd ../..
    fi
fi

if [ $input -eq 0 ] || [ $input -eq 6 ]
then
    # Model Inference
    if [ $LOCAL_BUILD == true ]
    then
        cd model_inference/tensorflow
        docker build --tag localhost:5000/tensorflow_model_inference .
        docker push localhost:5000/tensorflow_model_inference 
        cd ../pytorch
        docker build --tag localhost:5000/pytorch_model_inference .
        docker push localhost:5000/pytorch_model_inference
        cd ../..
    fi
fi

if [ $input -eq 0 ] || [ $input -eq 8 ]
then
    # Kafka Control Logger
    kubectl delete deploy kafka-control-logger -n $NAMESPACE

    if [ $LOCAL_BUILD == true ]
    then
        cd kafka_control_logger
        docker build --tag localhost:5000/kafka_control_logger .
        docker push localhost:5000/kafka_control_logger 
        cd ..
    fi

    kubectl apply -f kafka-control-logger-deployment.yaml -n $NAMESPACE
fi