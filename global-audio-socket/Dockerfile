# Step 1: Use the official Python 3.8.6 slim image
FROM python:3.8.6-slim

# Step 2: Set the working directory in the container
WORKDIR /app

# Step 3: Install required system dependencies including git, nano, and PostgreSQL client
RUN apt-get update && \
    apt-get install -y git nano libpq-dev gcc ffmpeg && \
    pip install --upgrade pip

# Step 4: Copy the requirements.txt and install the Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Change the working directory to `src/voip` before running the app
WORKDIR /app/src

CMD ["python","caller_ne.py"] 