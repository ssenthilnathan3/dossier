# Embedding Service

Python FastAPI service that generates vector embeddings for documents using sentence transformers.

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

## Environment Variables

- `QDRANT_URL`: Qdrant vector database URL
- `EMBEDDING_MODEL`: Sentence transformer model name (default: all-MiniLM-L6-v2)
- `BATCH_SIZE`: Embedding batch size (default: 32)