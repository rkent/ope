FROM verdaccio/verdaccio:2.7.4

# ope-verdaccio NPM offline repository
# Build with docker build -t ope-verdaccio .

# To copy to offline server use the setup tool

MAINTAINER R Kent James <rkent@caspia.org>
LABEL Description="NPM offline repository used by Open Prison Education" Vendor="openprisoneducation.com" Version="0.1"
COPY ./config.yaml /verdaccio/conf/config.yaml
COPY ./configOnline.yaml /verdaccio/conf/configOnline.yaml

ENV CONFIGFILE config.yaml
ENV PORT 4873
ENV PROTOCOL http
ENV APPDIR /usr/local/app
ENV VIRTUAL_HOST=verdaccio.ed

VOLUME ["/verdaccio/storage"]

CMD $APPDIR/bin/verdaccio --config /verdaccio/conf/$CONFIGFILE --listen $PROTOCOL://0.0.0.0:${PORT}
