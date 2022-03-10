@echo off
:init
echo Hi %USERNAME%, what do you want me to do?
goto select
:incorrecto
echo. Action not valid. Select again or close me.
:select
echo.
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
echo.
set /p action=Action: 
if %action%==0 goto all
if %action%==1 goto backend
if %action%==2 goto frontend
if %action%==3 goto tfexecutor
if %action%==4 goto pthexecutor
if %action%==5 goto model_training
if %action%==6 goto model_inference
if %action%==7 goto kafka
if %action%==8 goto kafka_control_logger
if %action%==9 goto zookeeper
if %action% GTR 9 goto incorrecto
if %action% LSS 0 goto incorrecto

:all
kubectl delete service backend
kubectl delete service frontend
kubectl delete service kafka-cluster
kubectl delete service pthexecutor
kubectl delete service tfexecutor
kubectl delete service zookeeper

kubectl apply -f backend-service.yaml
kubectl apply -f zookeeper-service.yaml
kubectl apply -f kafka-service.yaml
kubectl apply -f frontend-service.yaml
kubectl apply -f tf-executor-service.yaml
kubectl apply -f pth-executor-service.yaml

docker run -d -p 5000:5000 --restart=always --name registry registry:2 & ::It will throw an error if you already have a registry

:backend
:: Backend
kubectl get jobs --no-headers=true | awk "/model-training/{print $1}" | xargs kubectl delete jobs
:: You'll need Gow in order to run this instruction!! https://github.com/bmatzelle/gow    

kubectl delete deploy backend

cd backend
docker build --tag localhost:5000/backend .
docker push localhost:5000/backend 
cd ..

kubectl apply -f backend-deployment.yaml
if NOT %action%==0 goto end  

:frontend
:: Frontend (Heavy Load!)
kubectl delete deploy frontend

cd frontend
call npm install
call npm i -g @angular/cli
call ng build -c production
docker build --tag localhost:5000/frontend .
docker push localhost:5000/frontend
cd ..

kubectl apply -f frontend-deployment.yaml
if NOT %action%==0 goto end 

:tfexecutor
:: TensorFlow Executor 
kubectl delete deploy tfexecutor

cd mlcode_executor/tfexecutor 
docker build --tag localhost:5000/tfexecutor .
docker push localhost:5000/tfexecutor 
cd ../..
   
kubectl apply -f tf-executor-deployment.yaml
if NOT %action%==0 goto end  

:pthexecutor
:: PyTorch Executor 
kubectl delete deploy pthexecutor

cd mlcode_executor/pthexecutor
docker build --tag localhost:5000/pthexecutor .
docker push localhost:5000/pthexecutor 
cd ../..
   
kubectl apply -f pth-executor-deployment.yaml
if NOT %action%==0 goto end  

:model_training
:: Model training module
cd model_training/tensorflow 
docker build --tag localhost:5000/tensorflow_model_training .
docker push localhost:5000/tensorflow_model_training 
docker build -f Dockerfile_distributed --tag localhost:5000/distributed_model_training . & 
docker push localhost:5000/distributed_model_training
cd ../pytorch
docker build --tag localhost:5000/pytorch_model_training .
docker push localhost:5000/pytorch_model_training
cd ../..

if NOT %action%==0 goto end  

:model_inference
:: Model Inference
cd model_inference/tensorflow
docker build --tag localhost:5000/tensorflow_model_inference .
docker push localhost:5000/tensorflow_model_inference 
cd ../pytorch
docker build --tag localhost:5000/pytorch_model_inference .
docker push localhost:5000/pytorch_model_inference
cd ../..

if NOT %action%==0 goto end  

:kafka
kubectl delete pod kafka-pod
kubectl apply -f kafka-pod.yaml

if NOT %action%==0 goto end  


:kafka_control_logger
:: Kafka Control Logger
kubectl delete deploy kafka-control-logger

cd kafka_control_logger
docker build --tag localhost:5000/kafka_control_logger .
docker push localhost:5000/kafka_control_logger 
cd ..

kubectl apply -f kafka-control-logger-deployment.yaml
if NOT %action%==0 goto end  

:zookeeper

kubectl delete pod zookeeper
kubectl apply -f zookeeper-pod.yaml

if NOT %action%==0 goto end  

:end