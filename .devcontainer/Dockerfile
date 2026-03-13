FROM mcr.microsoft.com/devcontainers/python:3.14

RUN apt-get update && apt-get install -y libpcap-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

RUN pip install homeassistant home-assistant-frontend

WORKDIR /workspaces

EXPOSE 8123
