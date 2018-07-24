FROM ubuntu:16.04

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:jonathonf/python-3.6
RUN apt-get update
RUN apt-get install -y build-essential python3.6 python3-pip
RUN python3.6 -m pip install pip --upgrade
RUN python3.6 -m pip install wheel
