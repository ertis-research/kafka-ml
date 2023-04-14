set -ex

export BACKEND_PROXY_URL=${BACKEND_PROXY_URL:-"http://localhost:80"}
export BACKEND_URL=${BACKEND_URL:-"/api"}

envsubst < /usr/share/nginx/html/assets/env.template.js > /usr/share/nginx/html/assets/env.js 
envsubst '$BACKEND_PROXY_URL' < /default.template.conf > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
