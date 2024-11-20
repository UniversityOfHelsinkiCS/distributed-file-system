FROM registry.access.redhat.com/ubi9/python-311

WORKDIR /opt/app-root/src


COPY ./requirements.txt .

RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

COPY ./app ./app

CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
