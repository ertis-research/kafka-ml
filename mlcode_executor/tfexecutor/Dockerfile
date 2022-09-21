# GPU Accelerated
# FROM tensorflow/tensorflow:2.7.0-gpu

# CPU Only
FROM tensorflow/tensorflow:2.7.0

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# copy project
COPY . .

EXPOSE 8001

RUN chmod +x ./start.sh
CMD ["./start.sh"]