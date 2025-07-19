"""
Unit tests for document fetcher service
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from services.document_fetcher import DocumentFetcher, FetchResult, BatchFetchResult
from frappe_client import FrappeAPIError


class TestDocumentFetcher:
    """Test cases for DocumentFetcher"""
    
    @pytest.fixture
    def mock_frappe_client(self):
        """Mock Frappe client"""
        return Mock()
    
    @pytest.fixture
    def document_fetcher(self, mock_frappe_client):
        """Document fetcher with mocked client"""
        return DocumentFetcher(mock_frappe_client)
    
    def test_fetch_single_document_success(self, document_fetcher, mock_frappe_client):
        """Test successful single document fetch"""
        # Arrange
        mock_document = {
            "name": "TEST-001",
            "title": "Test Document",
            "description": "Test description"
        }
        mock_frappe_client.get_document.return_value = mock_document
        
        # Act
        result = document_fetcher.fetch_single_document("Test Doctype", "TEST-001")
        
        # Assert
        assert result.success is True
        assert result.document == mock_document
        assert result.doctype == "Test Doctype"
        assert result.docname == "TEST-001"
        assert result.error is None
        mock_frappe_client.get_document.assert_called_once_with("Test Doctype", "TEST-001")
    
    def test_fetch_single_document_with_fields(self, document_fetcher, mock_frappe_client):
        """Test single document fetch with specific fields"""
        # Arrange
        mock_document = {
            "title": "Test Document",
            "description": "Test description"
        }
        mock_frappe_client.get_document_fields.return_value = mock_document
        fields = ["title", "description"]
        
        # Act
        result = document_fetcher.fetch_single_document("Test Doctype", "TEST-001", fields)
        
        # Assert
        assert result.success is True
        assert result.document == mock_document
        mock_frappe_client.get_document_fields.assert_called_once_with("Test Doctype", "TEST-001", fields)
    
    def test_fetch_single_document_not_found(self, document_fetcher, mock_frappe_client):
        """Test single document fetch when document not found"""
        # Arrange
        mock_frappe_client.get_document.return_value = None
        
        # Act
        result = document_fetcher.fetch_single_document("Test Doctype", "TEST-001")
        
        # Assert
        assert result.success is False
        assert result.document is None
        assert result.error == "Document not found"
        assert result.doctype == "Test Doctype"
        assert result.docname == "TEST-001"
    
    def test_fetch_single_document_frappe_api_error(self, document_fetcher, mock_frappe_client):
        """Test single document fetch with Frappe API error"""
        # Arrange
        mock_frappe_client.get_document.side_effect = FrappeAPIError("API Error")
        
        # Act
        result = document_fetcher.fetch_single_document("Test Doctype", "TEST-001")
        
        # Assert
        assert result.success is False
        assert result.document is None
        assert "Frappe API error: API Error" in result.error
        assert result.doctype == "Test Doctype"
        assert result.docname == "TEST-001"
    
    def test_fetch_single_document_unexpected_error(self, document_fetcher, mock_frappe_client):
        """Test single document fetch with unexpected error"""
        # Arrange
        mock_frappe_client.get_document.side_effect = Exception("Unexpected error")
        
        # Act
        result = document_fetcher.fetch_single_document("Test Doctype", "TEST-001")
        
        # Assert
        assert result.success is False
        assert result.document is None
        assert "Unexpected error: Unexpected error" in result.error
    
    def test_fetch_documents_batch_success(self, document_fetcher, mock_frappe_client):
        """Test successful batch document fetch"""
        # Arrange
        mock_documents = [
            {"name": "TEST-001", "title": "Document 1", "description": "Desc 1"},
            {"name": "TEST-002", "title": "Document 2", "description": "Desc 2"}
        ]
        mock_frappe_client.get_documents.return_value = (mock_documents, 2)
        
        # Act
        result = document_fetcher.fetch_documents_batch("Test Doctype", limit=10)
        
        # Assert
        assert result.total_requested == 2
        assert result.total_fetched == 2
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert len(result.errors) == 0
        assert result.successful == mock_documents
    
    def test_fetch_documents_batch_with_fields_filtering(self, document_fetcher, mock_frappe_client):
        """Test batch fetch with field filtering"""
        # Arrange
        mock_documents = [
            {"name": "TEST-001", "title": "Document 1", "description": ""},  # Empty description
            {"name": "TEST-002", "title": "Document 2", "description": "Desc 2"},
            {"name": "TEST-003", "title": "", "description": "Desc 3"}  # Empty title
        ]
        mock_frappe_client.get_documents.return_value = (mock_documents, 3)
        fields = ["title", "description"]
        
        # Act
        result = document_fetcher.fetch_documents_batch("Test Doctype", fields=fields)
        
        # Assert
        assert result.total_requested == 3
        assert result.total_fetched == 3  # All documents have at least one content field
        assert len(result.successful) == 3
        
        # Check that empty fields are filtered out but documents with content are included
        doc_names = [doc["name"] for doc in result.successful]
        assert "TEST-001" in doc_names  # Has title
        assert "TEST-002" in doc_names  # Has both title and description
        assert "TEST-003" in doc_names  # Has description
        
        # Verify field filtering worked correctly
        for doc in result.successful:
            if doc["name"] == "TEST-001":
                assert "title" in doc and "description" not in doc  # Empty description filtered
            elif doc["name"] == "TEST-002":
                assert "title" in doc and "description" in doc  # Both fields present
            elif doc["name"] == "TEST-003":
                assert "title" not in doc and "description" in doc  # Empty title filtered
    
    def test_fetch_documents_batch_missing_name_field(self, document_fetcher, mock_frappe_client):
        """Test batch fetch with documents missing name field"""
        # Arrange
        mock_documents = [
            {"title": "Document 1"},  # Missing name field
            {"name": "TEST-002", "title": "Document 2"}
        ]
        mock_frappe_client.get_documents.return_value = (mock_documents, 2)
        
        # Act
        result = document_fetcher.fetch_documents_batch("Test Doctype")
        
        # Assert
        assert result.total_requested == 2
        assert result.total_fetched == 1  # Only one valid document
        assert len(result.successful) == 1
        assert len(result.failed) == 1
        assert result.failed[0].error == "Document missing 'name' field"
    
    def test_fetch_documents_batch_frappe_api_error(self, document_fetcher, mock_frappe_client):
        """Test batch fetch with Frappe API error"""
        # Arrange
        mock_frappe_client.get_documents.side_effect = FrappeAPIError("API Error")
        
        # Act
        result = document_fetcher.fetch_documents_batch("Test Doctype")
        
        # Assert
        assert result.total_requested == 0
        assert result.total_fetched == 0
        assert len(result.successful) == 0
        assert len(result.failed) == 0
        assert len(result.errors) == 1
        assert "Frappe API error: API Error" in result.errors[0]
    
    def test_fetch_documents_generator(self, document_fetcher, mock_frappe_client):
        """Test document generator with multiple batches"""
        # Arrange
        batch1 = [{"name": f"TEST-{i:03d}", "title": f"Doc {i}"} for i in range(1, 6)]
        batch2 = [{"name": f"TEST-{i:03d}", "title": f"Doc {i}"} for i in range(6, 9)]
        
        mock_frappe_client.get_documents.side_effect = [
            (batch1, 5),  # First batch: 5 documents
            (batch2, 3),  # Second batch: 3 documents (less than batch_size)
        ]
        
        # Act
        batches = list(document_fetcher.fetch_documents_generator("Test Doctype", batch_size=5))
        
        # Assert
        assert len(batches) == 2
        assert batches[0].total_fetched == 5
        assert batches[1].total_fetched == 3
        assert mock_frappe_client.get_documents.call_count == 2
    
    def test_get_document_count(self, document_fetcher, mock_frappe_client):
        """Test getting document count"""
        # Arrange
        mock_frappe_client.get_documents.return_value = ([{"name": "TEST-001"}], 100)
        
        # Act
        count = document_fetcher.get_document_count("Test Doctype")
        
        # Assert
        assert count == 100
        mock_frappe_client.get_documents.assert_called_once_with(
            doctype="Test Doctype",
            fields=["name"],
            filters=None,
            limit=1
        )
    
    def test_get_document_count_error(self, document_fetcher, mock_frappe_client):
        """Test getting document count with error"""
        # Arrange
        mock_frappe_client.get_documents.side_effect = Exception("Error")
        
        # Act
        count = document_fetcher.get_document_count("Test Doctype")
        
        # Assert
        assert count == 0
    
    def test_validate_doctype_fields_success(self, document_fetcher, mock_frappe_client):
        """Test successful field validation"""
        # Arrange
        sample_documents = [{"name": "TEST-001"}]
        sample_document = {
            "name": "TEST-001",
            "title": "Test",
            "description": "Test desc",
            "status": "Active"
        }
        mock_frappe_client.get_documents.return_value = (sample_documents, 1)
        mock_frappe_client.get_document.return_value = sample_document
        
        fields_to_validate = ["title", "description", "invalid_field"]
        
        # Act
        valid_fields, invalid_fields = document_fetcher.validate_doctype_fields(
            "Test Doctype", fields_to_validate
        )
        
        # Assert
        assert valid_fields == ["title", "description"]
        assert invalid_fields == ["invalid_field"]
    
    def test_validate_doctype_fields_no_documents(self, document_fetcher, mock_frappe_client):
        """Test field validation when no documents exist"""
        # Arrange
        mock_frappe_client.get_documents.return_value = ([], 0)
        fields_to_validate = ["title", "description"]
        
        # Act
        valid_fields, invalid_fields = document_fetcher.validate_doctype_fields(
            "Test Doctype", fields_to_validate
        )
        
        # Assert
        assert valid_fields == []
        assert invalid_fields == fields_to_validate
    
    def test_validate_doctype_fields_error(self, document_fetcher, mock_frappe_client):
        """Test field validation with error"""
        # Arrange
        mock_frappe_client.get_documents.side_effect = Exception("Error")
        fields_to_validate = ["title", "description"]
        
        # Act
        valid_fields, invalid_fields = document_fetcher.validate_doctype_fields(
            "Test Doctype", fields_to_validate
        )
        
        # Assert
        assert valid_fields == []
        assert invalid_fields == fields_to_validate


@pytest.mark.asyncio
class TestDocumentFetcherIntegration:
    """Integration tests for DocumentFetcher"""
    
    @pytest.fixture
    def mock_frappe_client_integration(self):
        """Mock Frappe client for integration tests"""
        client = Mock()
        
        # Mock realistic document data
        client.get_documents.return_value = ([
            {
                "name": "ITEM-001",
                "item_name": "Test Item 1",
                "description": "This is a test item description",
                "item_group": "Products"
            },
            {
                "name": "ITEM-002", 
                "item_name": "Test Item 2",
                "description": "",  # Empty description
                "item_group": "Services"
            }
        ], 2)
        
        return client
    
    def test_realistic_document_processing(self, mock_frappe_client_integration):
        """Test realistic document processing scenario"""
        # Arrange
        fetcher = DocumentFetcher(mock_frappe_client_integration)
        fields = ["item_name", "description", "item_group"]
        
        # Act
        result = fetcher.fetch_documents_batch(
            doctype="Item",
            fields=fields,
            filters={"item_group": "Products"},
            limit=10
        )
        
        # Assert
        assert result.total_requested == 2
        assert result.total_fetched == 2  # Both documents have at least one content field
        assert len(result.successful) == 2
        
        # Verify field filtering worked correctly
        item1 = next(doc for doc in result.successful if doc["name"] == "ITEM-001")
        assert "item_name" in item1
        assert "description" in item1
        assert "item_group" in item1
        
        item2 = next(doc for doc in result.successful if doc["name"] == "ITEM-002")
        assert "item_name" in item2
        assert "description" not in item2  # Empty field should be filtered out
        assert "item_group" in item2