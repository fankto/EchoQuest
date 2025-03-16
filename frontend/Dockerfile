FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* /app/
RUN npm ci

# Copy application code
COPY . /app/

# Build the application for development mode
RUN npm run build

# Expose port
EXPOSE 3000

# Run the application in development mode
CMD ["npm", "run", "dev"]