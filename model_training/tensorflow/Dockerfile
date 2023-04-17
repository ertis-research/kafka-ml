# --build-arg TFTAG=2.7.0-gpu for GPU version
ARG TFTAG=2.7.0 
FROM tensorflow/tensorflow:${TFTAG}

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

RUN chmod +x ./start.sh
CMD ["./start.sh"]