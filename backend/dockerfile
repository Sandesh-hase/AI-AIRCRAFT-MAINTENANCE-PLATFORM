# Use an official lightweight Python image
FROM python:3.12-slim

# Install uv using pip
RUN pip install uv

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt


# Copy the entire backend source code to the working directory
COPY . .

# Expose port 8000 so the app can be accessed from outside the container
EXPOSE 8000

# We bind to 0.0.0.0 to allow external connections
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]