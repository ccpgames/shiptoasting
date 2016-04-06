# ShipToasting flask frontend container

FROM python:3.5-alpine

RUN apk update && apk add patch gcc git musl-dev linux-headers libffi-dev openssl-dev tzdata ca-certificates
RUN pip install -U pip

COPY requirements.txt /src/
RUN pip install -qUr /src/requirements.txt

COPY shiptoasting /src/shiptoasting
COPY setup.py MANIFEST.in /src/
WORKDIR /src
RUN pip install -q .[deploy] && rm -rf /src

COPY config /app/
VOLUME /app
WORKDIR /app

RUN addgroup -S shiptoasting \
&& adduser -S -H -G shiptoasting -h /app -s /usr/sbin/nologin -D shiptoasting \
&& apk del patch gcc git musl-dev linux-headers

USER shiptoasting
EXPOSE 8080

ENV TZ=UTC
ENV FLASK_HOST_NAME http://localhost:8080
ENV EVE_SSO_CALLBACK http://localhost:8080/callback
ENV EVE_SSO_SCOPE publicData
ENV SHIPTOASTS_VISIBLE_MAX 50

ENV EVE_SSO_CONFIG ""
ENV GCLOUD_DATASET_ID ""
ENV GOOGLE_APPLICATION_CREDENTIALS ""
ENV FLASK_APP_SECRET_KEY ""

CMD gunicorn -c /app/config "shiptoasting.web:production()"
