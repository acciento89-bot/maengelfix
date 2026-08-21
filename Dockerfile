FROM python:3.12-alpine AS patched
WORKDIR /src
COPY server/ ./server/
COPY client/ ./client/
COPY scripts/upgrade_v022_case_reliability.py ./scripts/upgrade_v022_case_reliability.py
COPY scripts/upgrade_v023_google_play_billing.py ./scripts/upgrade_v023_google_play_billing.py
COPY scripts/upgrade_v024_google_play_rtdn.py ./scripts/upgrade_v024_google_play_rtdn.py
RUN python3 scripts/upgrade_v022_case_reliability.py \
  && python3 scripts/upgrade_v023_google_play_billing.py \
  && python3 scripts/upgrade_v024_google_play_rtdn.py \
  && test -f client/src/v022.css \
  && grep -q 'V022_CASE_DELETE_ENDPOINT' server/index.js \
  && grep -q 'V022_DEADLINE_ATOMIC_CLAIM' server/index.js \
  && grep -q 'V022_BRANDED_APP_MAIL' server/index.js \
  && grep -q 'V022_CASE_DELETE_ACTION' client/src/App.jsx \
  && grep -q 'V023_GOOGLE_PLAY_BILLING' server/index.js \
  && grep -q "app.post('/api/billing/google-play/verify'" server/index.js \
  && grep -q 'purchases/subscriptionsv2/tokens' server/index.js \
  && grep -q 'obfuscatedExternalAccountId' server/index.js \
  && grep -q 'V024_GOOGLE_PLAY_RTDN' server/index.js \
  && grep -q "app.post('/api/billing/google-play/rtdn'" server/index.js \
  && grep -q 'verifyGooglePlayRtdnOidc' server/index.js \
  && grep -q 'oauth2/v3/certs' server/index.js

FROM node:22-alpine AS web
WORKDIR /app/client
COPY --from=patched /src/client/package.json ./
RUN npm install
COPY --from=patched /src/client/ ./
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=patched /src/server/package.json ./server/package.json
RUN cd server && npm install --omit=dev
COPY --from=patched /src/server/ ./server/
RUN node --check server/index.js
COPY --from=web /app/client/dist ./public
RUN mkdir -p /data/uploads
EXPOSE 3000
CMD ["node", "server/index.js"]
