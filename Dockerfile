FROM python:3.9
RUN mkdir -p /opt/app
WORKDIR /opt/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY setup.py .
COPY src src
RUN pip install .
CMD python -m impfbot
