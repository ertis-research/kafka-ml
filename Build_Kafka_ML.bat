@echo off

@REM Set up this variable in order to change the namespace where Kafka-ML is going to be deployed.
@set NAMESPACE=kafkaml
@set LOCAL_BUILD=false

:init
echo Selected namespace "%NAMESPACE%" and local build is "%LOCAL_BUILD%"
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
kubectl create namespace %NAMESPACE%    
kubectl apply -f permissions-fix-yaml

kubectl delete service backend -n %NAMESPACE%
kubectl delete service frontend -n %NAMESPACE%
kubectl delete service kafka-cluster -n %NAMESPACE%
kubectl delete service pthexecutor -n %NAMESPACE%
kubectl delete service tfexecutor -n %NAMESPACE%
kubectl delete service zookeeper -n %NAMESPACE%

kubectl apply -f backend-service.yaml -n %NAMESPACE%
kubectl apply -f zookeeper-service.yaml -n %NAMESPACE%
kubectl apply -f kafka-service.yaml -n %NAMESPACE%
kubectl apply -f frontend-service.yaml -n %NAMESPACE%
kubectl apply -f tf-executor-service.yaml -n %NAMESPACE%
kubectl apply -f pth-executor-service.yaml -n %NAMESPACE%

:: If local_build is true, build the images locally, otherwise, build them on the cluster.
if %LOCAL_BUILD%==true goto local_build_registry
goto docker_registry
:local_build_registry
docker run -d -p 5000:5000 --restart=always --name registry registry:2 & ::It will throw an error if you already have a registry
:docker_registry

:zookeeper

kubectl delete pod zookeeper -n %NAMESPACE%
kubectl apply -f zookeeper-pod.yaml -n %NAMESPACE%

if NOT %action%==0 goto end  

:kafka
kubectl delete pod kafka-pod -n %NAMESPACE%
kubectl apply -f kafka-pod.yaml -n %NAMESPACE%

if NOT %action%==0 goto end  

:backend
:: Backend
for /f "tokens=1" %%a in ('kubectl get jobs --no-headers -n %NAMESPACE%') do kubectl delete job %%a -n %NAMESPACE%

kubectl delete deploy backend -n %NAMESPACE%

if %LOCAL_BUILD%==true goto local_build_backend
goto docker_backend
:local_build_backend
cd backend
docker build --tag localhost:5000/backend .
docker push localhost:5000/backend 
cd ..
:docker_backend

kubectl apply -f backend-deployment.yaml -n %NAMESPACE%
if NOT %action%==0 goto end  

:frontend
:: Frontend (Heavy Load!)
kubectl delete deploy frontend -n %NAMESPACE%

if %LOCAL_BUILD%==true goto local_build_frontend
goto docker_frontend
:local_build_frontend
cd frontend
call npm install
call npm i -g @angular/cli
call ng build -c production
docker build --tag localhost:5000/frontend .
docker push localhost:5000/frontend
cd ..
:docker_frontend

kubectl apply -f frontend-deployment.yaml -n %NAMESPACE%
if NOT %action%==0 goto end 

:tfexecutor
:: TensorFlow Executor 
kubectl delete deploy tfexecutor -n %NAMESPACE%

if %LOCAL_BUILD%==true goto local_build_tfexecutor
goto docker_tfexecutor
:local_build_tfexecutor
cd mlcode_executor/tfexecutor 
docker build --tag localhost:5000/tfexecutor .
docker push localhost:5000/tfexecutor 
cd ../..
:docker_tfexecutor
   
kubectl apply -f tf-executor-deployment.yaml -n %NAMESPACE%
if NOT %action%==0 goto end  

:pthexecutor
:: PyTorch Executor 
kubectl delete deploy pthexecutor -n %NAMESPACE%

if %LOCAL_BUILD%==true goto local_build_ptexecutor
goto docker_ptexecutor
:local_build_ptexecutor
cd mlcode_executor/pthexecutor
docker build --tag localhost:5000/pthexecutor .
docker push localhost:5000/pthexecutor 
cd ../..
:docker_ptexecutor
   
kubectl apply -f pth-executor-deployment.yaml -n %NAMESPACE%
if NOT %action%==0 goto end  

:model_training
:: Model training module

if %LOCAL_BUILD%==true goto local_build_trainingtf
goto docker_trainingtf
:local_build_trainingtf
cd model_training/tensorflow 
docker build --tag localhost:5000/tensorflow_model_training .
docker push localhost:5000/tensorflow_model_training 
cd ../pytorch
docker build --tag localhost:5000/pytorch_model_training .
docker push localhost:5000/pytorch_model_training
cd ../..
:docker_trainingtf

if NOT %action%==0 goto end  

:model_inference
:: Model Inference

if %LOCAL_BUILD%==true goto local_build_inferencetf
goto docker_inferencetf
:local_build_inferencetf
cd model_inference/tensorflow
docker build --tag localhost:5000/tensorflow_model_inference .
docker push localhost:5000/tensorflow_model_inference 
cd ../pytorch
docker build --tag localhost:5000/pytorch_model_inference .
docker push localhost:5000/pytorch_model_inference
cd ../..
:docker_inferencetf

if NOT %action%==0 goto end  

:kafka_control_logger
:: Kafka Control Logger
kubectl delete deploy kafka-control-logger -n %NAMESPACE%

if %LOCAL_BUILD%==true goto local_build_kafka_control_logger
goto docker_kafka_control_logger
:local_build_kafka_control_logger
cd kafka_control_logger
docker build --tag localhost:5000/kafka_control_logger .
docker push localhost:5000/kafka_control_logger 
cd ..
:docker_kafka_control_logger

kubectl apply -f kafka-control-logger-deployment.yaml -n %NAMESPACE%
if NOT %action%==0 goto end  

:end