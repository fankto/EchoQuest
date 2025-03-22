FROM node:18-alpine

WORKDIR /app

# Set environment variables
ENV NEXT_PUBLIC_API_URL=http://localhost:8000

# Install dependencies
COPY package.json /app/
RUN npm install

# Copy application code
COPY . /app/

# Expose port
EXPOSE 3000

# Run the application in development mode
CMD ["npm", "run", "dev"]
