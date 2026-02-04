# pull official base image
FROM python:3.8.6
# FROM python:3.7.7-slim-stretch # for Raspberry

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
RUN pip install uv
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN uv pip install -r requirements.txt --prerelease=allow --system

# copy project
COPY . /usr/src/app/

EXPOSE 8000

RUN chmod +x ./start.sh
CMD ["./start.sh"]