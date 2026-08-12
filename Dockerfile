FROM node:22-alpine AS web
WORKDIR /app/client
COPY client/package.json ./
RUN npm install
COPY client/ ./
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY server/package.json ./server/package.json
RUN cd server && npm install --omit=dev
COPY server/ ./server/
COPY --from=web /app/client/dist ./public
RUN mkdir -p /data/uploads
EXPOSE 3000
CMD ["node", "server/index.js"]
