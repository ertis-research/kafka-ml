# pull official base image
FROM python:3.8.6

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .

RUN chmod +x ./start.sh
CMD ["./start.sh"]