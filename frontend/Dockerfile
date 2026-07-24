# pnpm version is pinned via the "packageManager" field in package.json
# (pnpm@10.33.0). corepack reads that field and provisions the exact version,
# so the build is reproducible and immune to newer pnpm releases changing
# default policies (e.g. the 24h minimum-release-age / ignored-builds checks
# introduced in pnpm 11 that broke frozen installs of a freshly-published dep).
FROM node:22-alpine AS deps
WORKDIR /app
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM node:22-alpine AS build
WORKDIR /app
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable pnpm
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --chown=node:node --from=build /app/.next/standalone ./
COPY --chown=node:node --from=build /app/.next/static ./.next/static
COPY --chown=node:node --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
