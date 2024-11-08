FROM nginx:mainline-alpine

ARG GENERATED_DOCS_PATH

# Copy generated files to nginx default html directory
COPY $GENERATED_DOCS_PATH /usr/share/nginx/html
# Copy nginx custom configuration to default directory
RUN rm /etc/nginx/conf.d/*

ADD nginx.conf /etc/nginx/nginx.conf