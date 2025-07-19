# LLM Service

Python FastAPI service that provides LLM-based question answering using Ollama.

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

## Environment Variables

- `OLLAMA_URL`: Ollama server URL (default: http://localhost:11434)
- `DEFAULT_MODEL`: Default Ollama model to use (default: llama2)

## Ollama Models

The service supports any model available in Ollama. Popular options:
- `llama2`: General purpose model
- `codellama`: Code-focused model
- `mistral`: Fast and efficient model
- `phi`: Microsoft's small language model

To pull a model in Ollama:
```bash
ollama pull llama2
```