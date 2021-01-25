# pull official base image
# FROM tensorflow/tensorflow:2.0.1-py3
FROM tensorflow/tensorflow:2.2.0
# FROM python:3.7.7-slim-stretch # for Raspberry

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

EXPOSE 8000

RUN chmod +x ./start.sh
CMD ["./start.sh"]