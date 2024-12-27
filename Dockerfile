FROM python:3.10-slim
ENV PYTHINUNBUFFERED=1

RUN apt-get update && apt-get install -y netcat-openbsd

WORKDIR /trader
COPY requirements.txt /trader/requirements.txt
COPY entrypoint.sh /trader/entrypoint.sh

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y postgresql-client

RUN chmod +x /trader/entrypoint.sh
ENTRYPOINT ["sh", "/trader/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
 

COPY . /trader/




