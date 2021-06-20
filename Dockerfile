FROM python:3.9
RUN mkdir -l /opt/app
WORKDIR /opt/app
COPY src/ setup.py .
RUN pip install .
CMD python -m impfbot
