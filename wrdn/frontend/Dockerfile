FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:18000

ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NODE_ENV=production
ENV PORT=3000

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]