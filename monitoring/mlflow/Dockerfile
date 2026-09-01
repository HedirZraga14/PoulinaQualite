FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir mlflow==2.16.2

WORKDIR /app

RUN mkdir -p /mlflow/artifacts /mlflow/data

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/data/mlflow.db", "--artifacts-destination", "/mlflow/artifacts"]
