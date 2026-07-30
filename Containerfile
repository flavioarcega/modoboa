#========================
FROM docker.io/library/debian:13-slim AS base
#========================

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update --fix-missing && apt-get install -y \
  coreutils       \
  libcairo2-dev   \
  libffi-dev      \
  libjpeg-dev     \
  libmagic1       \
  librrd-dev      \
  libssl-dev      \
  libxml2-dev     \
  libxslt-dev     \
  pkg-config      \
  python3-minimal \
  rrdtool


#========================
FROM base as build
#========================

RUN apt-get install -y \
  pkg-config    \
  python3-dev   \
  python3-pip   \
  yarnpkg

COPY . /usr/src/modoboa

WORKDIR /usr/src/modoboa/frontend
RUN yarnpkg config set -H globalFolder /root/.cache/yarn && yarnpkg && yarnpkg build

ENV SETUPTOOLS_SCM_PRETEND_VERSION=2.9.2.dev
RUN pip install --root-user-action=ignore --break-system-packages gunicorn psycopg[binary] /usr/src/modoboa


#========================
FROM base as instance
#========================

RUN apt-get autoremove && apt-get autoclean

COPY --from=build /usr/local/lib /usr/local/lib
COPY --from=build /usr/local/bin /usr/local/bin

RUN useradd -s /bin/bash -mU modoboa
USER modoboa
WORKDIR /home/modoboa
ENV PATH="/home/modoboa/.local/bin:${PATH}"

ARG DOMAIN
ARG DBURL
ARG REDIS_HOST

RUN modoboa-admin.py deploy instance \
  --timezone 'America/Sao_Paulo' \
  --domain ${DOMAIN} \
  --redis ${REDIS_HOST} \
  --dburl default:${DBURL} \
  --collectstatic --devel

RUN mv instance/media instance/www/media

WORKDIR /home/modoboa/instance

EXPOSE 8000

CMD ["gunicorn", "instance.wsgi"]
