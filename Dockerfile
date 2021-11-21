FROM python:3.9

RUN apt-get update && \
    apt-get install -y locales && \
    sed -i -e 's/# de_DE.UTF-8 UTF-8/de_DE.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

RUN mkdir -p /opt/app
WORKDIR /opt/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY setup.py .
COPY src src
RUN pip install .

CMD python -m impfbot
