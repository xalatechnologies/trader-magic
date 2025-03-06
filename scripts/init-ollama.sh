#!/bin/sh
# Script to wait for Ollama server and pull the model

# Default to llama3 if not set
MODEL="${OLLAMA_MODEL:-llama3.2:latest}"
echo "Will pull model: $MODEL"

# Wait for Ollama to be ready
echo "Waiting for Ollama server to be ready..."
for i in $(seq 1 30); do
  if curl -s http://ollama:11434/api/version > /dev/null 2>&1; then
    echo "Ollama server is ready!"
    echo "Pulling model: $MODEL"
    curl -X POST http://ollama:11434/api/pull -d "{\"name\":\"$MODEL\"}"
    echo "Model pull initiated. This may take some time to complete."
    exit 0
  fi
  echo "Waiting for Ollama server (attempt $i/30)..."
  sleep 5
done

# If we get here, we timed out
echo "Timed out waiting for Ollama server"
exit 1