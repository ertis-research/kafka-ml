FROM nginx:1.18-alpine

# Copy source
COPY /dist/autofront /usr/share/nginx/html

# Copy configuration file
COPY ./nginx-custom.conf /etc/nginx/conf.d/default.conf

# Copy environment vars and execute the server
CMD ["/bin/sh",  "-c",  "envsubst < /usr/share/nginx/html/assets/env.template.js > /usr/share/nginx/html/assets/env.js && exec nginx -g 'daemon off;'"]