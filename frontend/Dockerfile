# Use official lightweight Node.js 20 LTS Alpine image
FROM node:20-alpine

WORKDIR /app

# Copy dependency specifications first to leverage Docker layer caching
COPY package.json package-lock.json ./

# Install dependencies deterministically
RUN npm ci

# Copy application source code
COPY . .

# Expose Vite default dev server port
EXPOSE 5173

# Run Vite dev server bound to 0.0.0.0 for container port forwarding
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
