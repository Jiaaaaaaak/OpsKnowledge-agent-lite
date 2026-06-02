FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
# Use --include=optional to ensure Rolldown's native bindings are installed
RUN npm ci --include=optional

COPY . .
RUN npm run build

EXPOSE 8501

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8501"]
