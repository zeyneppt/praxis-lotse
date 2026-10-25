FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
# Editable install: `app` wird aus /app/app importiert, nicht aus site-packages,
# damit app/db.py die Migrationen unter /app/alembic findet.
RUN pip install --no-cache-dir -e ".[dev]"

# Embedding-Modell beim Build laden, nicht beim ersten Request (Spec 003).
# Standard wie in .env.example und app/config.py.
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} FASTEMBED_CACHE_PATH=/opt/fastembed
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(os.environ['EMBEDDING_MODEL'])"
# Danach kein Netzwerkzugriff des Modell-Hubs mehr.
ENV HF_HUB_OFFLINE=1

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
