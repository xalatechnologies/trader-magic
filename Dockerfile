FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt setup.py ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install the package in development mode
RUN pip install -e .

CMD ["python", "src/main.py"]