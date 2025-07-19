# Ingestion Service

Python FastAPI service that processes documents from Frappe and manages ingestion workflows.

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection URL
- `REDIS_URL`: Redis connection URL
- `FRAPPE_URL`: Frappe instance URL
- `FRAPPE_API_KEY`: Frappe API key
- `FRAPPE_API_SECRET`: Frappe API secret