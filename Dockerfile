FROM registry.access.redhat.com/ubi9/python-311

WORKDIR /opt/app-root/src

COPY . .

RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

#CMD ["fastapi", "run", "src/main.py", "--port", "80"]
CMD ["sleep", "infinity"]
