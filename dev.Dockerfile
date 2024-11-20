FROM python:3.11-slim

WORKDIR /opt/app-root/src

COPY ./requirements.txt .

RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

COPY ./app ./app

CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0"]
