# Linux x86_64 so the Moss native runtime (inferedge-moss-core) wheel installs.
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir "moss>=1.2" "fastapi>=0.110" "uvicorn[standard]>=0.29"
COPY server.py .

EXPOSE 8077
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8077"]
