FROM node:14 as angular-builder
COPY package.json *lock* /build/
WORKDIR /build
RUN npm install
COPY . /build
RUN npm run build

FROM nginx:1.18-alpine
COPY --from=angular-builder /build/dist/autofront /usr/share/nginx/html
COPY ./nginx-custom.conf /default.template.conf
COPY --chown=777 start.sh /start.sh
CMD ["sh", "/start.sh"]
