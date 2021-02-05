FROM ubuntu:focal

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip 

WORKDIR /norconf

COPY . .

RUN pip3 install -r requirements.txt

CMD ["black", "norconf.py"]

