FROM instructure/ruby-passenger:2.4
##FROM instructure/canvas-lms:stable

LABEL maintainer="Ray Pulsipher <ray@cmagic.biz>"
LABEL description="Canvas LMS by Instructure - Image for Open Prison Education"
LABEL vendor="openprisoneducation.com"
LABEL version="0.5"

# ope-canvas - Canvas LMS System
# Build with docker build -t ope-canvas .

#TODO - Auto disable student collaboration features

#INSTRUCTIONS
# Build the canvas container and run it with the docker-compose command
# View the canvas website to set your admin password and configure.

ENV APP_HOME /usr/src/app/
ENV RAILS_ENV "production"
ENV NGINX_MAX_UPLOAD_SIZE 10g
ENV YARN_VERSION 1.3.2-1

# Work around github.com/zertosh/v8-compile-cache/issues/2
# This can be removed once yarn pushes a release including the fixed version
# of v8-compile-cache.
ENV DISABLE_V8_COMPILE_CACHE 1
USER root

RUN curl -sL https://deb.nodesource.com/setup_8.x | bash - \
  && curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - \
  && echo "deb https://dl.yarnpkg.com/debian/ stable main" > /etc/apt/sources.list.d/yarn.list \
  && printf 'path-exclude /usr/share/doc/*\npath-exclude /usr/share/man/*' > /etc/dpkg/dpkg.cfg.d/01_nodoc \
  && echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
  && curl -sS https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
  && apt-get update -qq \
  && apt-get install -qqy --no-install-recommends \
       nodejs \
       yarn="$YARN_VERSION" \
       libxmlsec1-dev \
       python-lxml \
       libicu-dev \
       postgresql-client-9.5 \
       unzip \
       fontforge \
       dos2unix \
       supervisor \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /home/docker/.gem/ruby/$RUBY_MAJOR.0

RUN if [ -e /var/lib/gems/$RUBY_MAJOR.0/gems/bundler-* ]; then BUNDLER_INSTALL="-i /var/lib/gems/$RUBY_MAJOR.0"; fi \
  && gem uninstall --all --ignore-dependencies --force $BUNDLER_INSTALL bundler \
  && gem install bundler --no-document -v 1.15.2 \
  && find $GEM_HOME ! -user docker | xargs chown docker:docker

# Make sure this runs during build, will also run at at startup later
#ENV CANVAS_BUILD_CONCURRENCY=1

WORKDIR $APP_HOME

# Git checkout instead of docker build from source dir
#COPY Gemfile      ${APP_HOME}
#COPY Gemfile.d    ${APP_HOME}Gemfile.d
#COPY config       ${APP_HOME}config
#COPY gems         ${APP_HOME}gems
#COPY packages     ${APP_HOME}packages
#COPY script       ${APP_HOME}script
#COPY package.json ${APP_HOME}
#COPY yarn.lock    ${APP_HOME}

RUN cd ${APP_HOME} \
    && git clone https://github.com/instructure/canvas-lms.git . \
    && git checkout stable
#   release/2018-02-17.04

# We will need sfnt2woff in order to build fonts
#COPY build/vendor/woff-code-latest.zip ./
RUN cd build/vendor \
  && unzip woff-code-latest.zip -d woff \
  && cd woff \
  && make \
  && cp sfnt2woff /usr/local/bin \
  && cd - \
  && rm -rf woff*

RUN find gems packages -type d ! -user docker -print0 | xargs -0 chown -h docker:docker

USER docker

RUN bundle install --jobs 8 \
  && yarn install --pure-lockfile
USER root

RUN mkdir -p .yardoc \
             app/stylesheets/brandable_css_brands \
             client_apps/canvas_quizzes/node_modules \
             gems/canvas_i18nliner/node_modules \
             gems/selinimum/node_modules \
             log \
             node_modules \
             public/dist \
             public/doc/api \
             public/javascripts/client_apps \
             public/javascripts/compiled \
             tmp \
             /home/docker/.bundler/ \
             /home/docker/.cache/yarn \
             /home/docker/.gem/ \
  && find ${APP_HOME} /home/docker ! -user docker -print0 | xargs -0 chown -h docker:docker


# INSTALL QTIMigrationTool
RUN mkdir ${APP_HOME}/vendor \
	&& cd ${APP_HOME}/vendor \
	&& git clone https://github.com/instructure/QTIMigrationTool.git QTIMigrationTool \
	&& chmod +x QTIMigrationTool/migrate.py
    
#RUN rm -rf node_modules \
#    && rm -rf gems/**/node_modules \
#    && npm cache clean    

USER docker
# TODO: switch to canvas:compile_assets_dev once we stop using this Dockerfile in production/e2e
RUN COMPILE_ASSETS_NPM_INSTALL=0 bundle exec rake canvas:compile_assets


#USER root
#RUN rm -rf node_modules
#RUN npm install
#RUN $GEM_HOME/bin/bundle exec rake canvas:compile_assets --trace
#RUN echo "Settings file permissions on node_modules..." \
#    && chown -R docker:docker /usr/src/app/node_modules


USER docker


LABEL rebuild=34

COPY amazon_s3.yml config/amazon_s3.yml
COPY delayed_jobs.yml config/delayed_jobs.yml
COPY file_store.yml config/file_store.yml
COPY security.yml.tmpl config/security.yml.tmpl
COPY external_migration.yml config/external_migration.yml

COPY database.yml.tmpl config/database.yml.tmpl
COPY redis.yml config/redis.yml
COPY cache_store.yml config/cache_store.yml
COPY production-local.rb config/environments/production-local.rb
COPY outgoing_mail.yml.tmpl config/outgoing_mail.yml.tmpl

COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY domain.yml.tmpl /usr/src/app/config/domain.yml.tmpl
COPY dbinit.sh /usr/src/dbinit.sh
COPY start.sh /usr/src/start.sh
COPY ope.rake lib/tasks/ope.rake

USER root

RUN echo "Settings file permissions..." \
    && mkdir /tmp/attachment_fu \
    && chown -R docker:docker /tmp/attachment_fu /usr/src/app/log \
    && chmod 755 /usr/src/*.sh \
    && dos2unix /usr/src/*.sh \
    && chown -R docker:docker /usr/src/*.sh /usr/src/app/config /usr/src/app/vendor /usr/src/app/lib/tasks/ope.rake
    
# Stay root at the end - supervisor will switch back to docker user
VOLUME ["/usr/src/app/tmp", "/usr/src/app/log", "/tmp"]
EXPOSE 3000

CMD ["/usr/src/start.sh"]
