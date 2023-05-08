FROM node:14 as angular-builder
COPY package.json *lock* /build/
WORKDIR /build
RUN npm install
COPY src e2e browserslist *.json *.js /build
RUN npx ng build --prod

FROM nginx:1.18-alpine
COPY --from=angular-builder /build/dist/autofront /usr/share/nginx/html
COPY ./nginx-custom.conf /default.template.conf
COPY --chown=777 start.sh /start.sh
CMD ["sh", "/start.sh"]
