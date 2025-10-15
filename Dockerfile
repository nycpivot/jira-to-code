FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the source directory into the image
COPY src/ ./src/

# expose uvicorn on 8080
EXPOSE 8080

# run your FastAPI app (module path uses src/)
ENV PYTHONPATH=/app/src
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8080","--app-dir","/app/src","--workers","2","--proxy-headers","--forwarded-allow-ips","*"]
