# Build context: repository root (see docker-compose.rpg.prod.yml)
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY rpg-frontend/package.json ./
RUN npm install
COPY rpg-frontend/ .
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY rpg-nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
