# syntax=docker/dockerfile:1

# -----------------------------------------------------------------------------
# Stage 1 — build the Vite/React app into static assets.
# -----------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

# Install deps first (better layer caching).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# API base defaults to "/api" (proxied by nginx to the backend), so no
# build-time backend URL is required.
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2 — serve the static build with nginx and reverse-proxy /api -> backend.
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
