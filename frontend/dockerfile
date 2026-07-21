# Use an official lightweight Node.js image
FROM node:20-alpine

# Set the working directory inside the container
WORKDIR /app

COPY package.json package-lock.json ./

# Install frontend dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY . .

CMD ["npm", "run", "dev", "--", "--host"]