FROM python:3.11-slim

WORKDIR /app/frontend

# Copy only the frontend requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the frontend code
COPY . .

# Set PYTHONPATH to include parent directory
ENV PYTHONPATH=/app

CMD ["python", "app.py"]