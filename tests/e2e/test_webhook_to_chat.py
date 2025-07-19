import os
import time
import pytest
import httpx

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8081/webhook")

@pytest.mark.asyncio
async def test_webhook_to_chat_flow():
    """
    End-to-end test: webhook event → ingestion → embedding → query → LLM → chat response
    """
    # 1. Simulate webhook event (document upload or update)
    webhook_payload = {
        "event": "document_uploaded",
        "data": {
            "doctype": "TestDoc",
            "docname": "DOC-001",
            "content": "This is a test document for E2E testing."
        }
    }
    async with httpx.AsyncClient() as client:
        # TODO: Authenticate if needed
        webhook_resp = await client.post(WEBHOOK_URL, json=webhook_payload)
        assert webhook_resp.status_code in (200, 202)

    # 2. Wait for ingestion and embedding to complete (poll or sleep)
    time.sleep(5)  # TODO: Replace with polling ingestion status

    # 3. Send a chat query via API gateway
    chat_payload = {
        "query": "What is the test document about?",
        "context_chunks": [],
        "model": "llama2"
    }
    # TODO: Add JWT auth header
    headers = {}
    async with httpx.AsyncClient() as client:
        chat_resp = await client.post(f"{API_GATEWAY_URL}/llm", json=chat_payload, headers=headers)
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        # TODO: Assert the response contains expected content
        assert "answer" in data
        # Optionally: assert "test document" in data["answer"].lower() 