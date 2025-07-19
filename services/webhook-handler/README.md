# Webhook Handler Service

Node.js service that receives and validates Frappe webhooks, then publishes them to Redis for processing.

## Development

```bash
npm install
npm run dev
```

## Environment Variables

- `PORT`: Server port (default: 3001)
- `REDIS_URL`: Redis connection URL
- `WEBHOOK_SECRET`: Secret for webhook signature validation
- `NODE_ENV`: Environment (development/production)