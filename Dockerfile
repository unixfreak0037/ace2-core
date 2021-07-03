FROM python:3.9-buster
ENV TZ UTC
ENV DEBIAN_FRONTEND noninteractive
ARG ACE_UID=1000
ARG ACE_GID=1000
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get -y install apt-utils && apt-get -y install cargo
RUN groupadd ace -g $ACE_GID && useradd -g ace -m -d /opt/ace -s /bin/bash -u $ACE_UID ace

USER ace
WORKDIR /opt/ace
COPY requirements.txt .
COPY requirements-dev.txt .
RUN python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -r requirements-dev.txt
COPY ace2 ace2
COPY ace ace
COPY ansistrm.py .
COPY etc etc
COPY pytest.ini .
COPY tests tests
CMD /bin/bash
