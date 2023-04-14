FROM python:3.11-alpine

# Copy the requirements file first to take advantage of Docker's caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the files
COPY ./kebabmeister /app/kebabmeister
WORKDIR /app

# Run the app
CMD ["python", "-m", "kebabmeister", "-c", "/data/config.json"]
