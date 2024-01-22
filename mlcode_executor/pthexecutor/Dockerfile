# --build-arg BASEIMG=pytorch/pytorch:1.10.0-cuda11.3-cudnn8-runtime for GPU version
ARG BASEIMG=python:3.11.7
FROM ${BASEIMG}

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

# copy project
COPY . /usr/src/app/

EXPOSE 8002

RUN chmod +x ./start.sh
CMD ["./start.sh"]