FROM python:3.9-buster
ENV TZ UTC
ENV DEBIAN_FRONTEND noninteractive
ENV VIRTUAL_ENV=/venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH:."
ARG ACE_UID=1000
ARG ACE_GID=1000
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get -y install apt-utils && apt-get -y install cargo
RUN groupadd ace -g $ACE_GID && useradd -g ace -m -d /opt/ace -s /bin/bash -u $ACE_UID ace
RUN mkdir /venv && chown ace:ace /venv

USER ace
WORKDIR /opt/ace
COPY requirements.txt .
COPY requirements-dev.txt .
RUN python3 -m venv /venv && pip install -r requirements.txt && pip install -r requirements-dev.txt
COPY --chown=ace:ace acecli acecli
COPY --chown=ace:ace ace ace
COPY --chown=ace:ace ansistrm.py .
COPY --chown=ace:ace etc etc
COPY --chown=ace:ace execute_tests.sh .
COPY --chown=ace:ace pytest.ini .
COPY --chown=ace:ace tests tests
COPY --chown=ace:ace gunicorn_conf.py .
COPY --chown=ace:ace start.sh .
RUN mkdir /opt/ace/data
CMD /opt/ace/start.sh
