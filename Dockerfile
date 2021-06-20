FROM python:3.9
RUN mkdir -p /opt/app
WORKDIR /opt/app
COPY setup.py ./
COPY src src
RUN ls -l
RUN pip install .
CMD python -m impfbot
