FROM python:3.10-slim
ENV PYTHINUNBUFFERED=1
WORKDIR /trader
COPY requirements.txt /trader/

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . /trader/




