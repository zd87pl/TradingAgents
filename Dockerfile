# Use the official Python image as a parent image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements-docker.txt .

# Install any needed packages specified in requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy the entire project to the working directory
COPY . .

# Environment variables for API keys and other configurations
ARG OPENAI_API_KEY
ARG ALPHA_VANTAGE_API_KEY
ARG LLM_PROVIDER

# Expose port 8000 for Chainlit
EXPOSE 8000

