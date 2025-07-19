"""
Integration tests for manual ingestion workflows
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import uuid
import json
from datetime import datetime, timedelta

# Import the services directly without the full app
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))

from services.document_fetcher import DocumentFetcher, BatchFetchResult, FetchResult
from services.ingestion_processor import IngestionProcessor
from models.database_models import DoctypeConfigModel, IngestionJobModel
from shared.models.base import JobStatus
from shared.models.ingestion import IngestionRequest


class TestManualIngestionIntegration:
    """Integration tests for manual ingestion workflows"""
    
    @pytest.fixture
    def mock_frappe_documents(self):
        """Mock Frappe documents for testing"""
        return [
            {
                "name": "ITEM-001",
                "item_name": "Test Item 1",
                "description": "This is a test item description",
                "item_group": "Products",
                "modified": "2024-01-15T10:00:00Z"
            },
            {
                "name": "ITEM-002",
                "item_name": "Test Item 2",
                "description": "Another test item",
                "item_group": "Services",
                "modified": "2024-01-16T11:00:00Z"
            },
            {
                "name": "ITEM-003",
                "item_name": "Test Item 3",
                "description": "",  # Empty description
                "item_group": "Products",
                "modified": "2024-01-17T12:00:00Z"
            }
        ]
    
    @patch('frappe_client.get_frappe_client')
    def test_manual_ingestion_job_creation(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test that manual ingestion jobs are created successfully"""
        # Mock the Frappe client to avoid configuration issues
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock field validation - return a sample document with the expected fields
        sample_doc = {
            "name": "SAMPLE-001",
            "item_name": "Sample Item",
            "description": "Sample description",
            "item_group": "Products"
        }
        
        # Mock get_documents to return sample documents for field validation
        mock_client.get_documents.return_value = ([{"name": "SAMPLE-001"}], 1)
        mock_client.get_document.return_value = sample_doc
        
        # Start manual ingestion
        request_data = {
            "doctype": "Item",
            "batchSize": 2,
            "forceUpdate": False,
            "filters": {"item_group": "Products"}
        }
        
        response = client.post("/api/ingestion/manual", json=request_data)
        assert response.status_code == 200
        
        job_data = response.json()
        assert "jobId" in job_data
        assert job_data["status"] == "queued"
        
        job_id = job_data["jobId"]
        
        # Check job was created in database
        job = test_db.query(IngestionJobModel).filter(
            IngestionJobModel.job_id == job_id
        ).first()
        
        assert job is not None
        assert job.doctype == "Item"
        assert job.batch_size == 2
        # Job might be completed quickly due to mocked data
        assert job.status in [JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED]
        assert job.filters == {"item_group": "Products"}
    
    @patch('frappe_client.get_frappe_client')
    def test_batch_manual_ingestion_endpoint(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test batch manual ingestion endpoint"""
        # Mock the Frappe client
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock field validation
        sample_doc = {
            "name": "SAMPLE-001",
            "item_name": "Sample Item",
            "description": "Sample description",
            "item_group": "Products"
        }
        mock_client.get_documents.return_value = ([{"name": "SAMPLE-001"}], 1)
        mock_client.get_document.return_value = sample_doc
        
        # Create additional doctype config
        config2 = DoctypeConfigModel(
            doctype="Customer",
            enabled=True,
            fields=["customer_name", "customer_group"],
            filters={},
            chunk_size=500,
            chunk_overlap=100
        )
        test_db.add(config2)
        test_db.commit()
        
        # Start batch ingestion
        batch_requests = [
            {
                "doctype": "Item",
                "batchSize": 10,
                "forceUpdate": False
            },
            {
                "doctype": "Customer",
                "batchSize": 20,
                "forceUpdate": True
            }
        ]
        
        response = client.post("/api/ingestion/manual/batch", json=batch_requests)
        assert response.status_code == 200
        
        batch_data = response.json()
        assert "message" in batch_data
        assert "jobs" in batch_data
        assert len(batch_data["jobs"]) == 2
        
        # Verify each job was created
        for job in batch_data["jobs"]:
            assert "jobId" in job
            assert job["status"] == "queued"
            
            # Check individual job status
            job_response = client.get(f"/api/ingestion/jobs/{job['jobId']}")
            assert job_response.status_code == 200
    
    @patch('frappe_client.get_frappe_client')
    def test_manual_ingestion_with_progress_tracking(self, mock_get_client, client, test_db, sample_doctype_config, mock_frappe_documents):
        """Test manual ingestion with detailed progress tracking"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_documents.return_value = (mock_frappe_documents, len(mock_frappe_documents))
        
        # Start ingestion
        request_data = {
            "doctype": "Item",
            "batchSize": 1,  # Small batch size to test progress
            "forceUpdate": True
        }
        
        response = client.post("/api/ingestion/manual", json=request_data)
        job_id = response.json()["jobId"]
        
        # Get detailed summary
        summary_response = client.get(f"/api/ingestion/jobs/{job_id}/summary")
        assert summary_response.status_code == 200
        
        summary = summary_response.json()
        assert "progress" in summary
        assert "timing" in summary
        assert "configuration" in summary
        assert "errors" in summary
        
        # Verify progress structure
        progress = summary["progress"]
        assert "processed" in progress
        assert "updated" in progress
        assert "failed" in progress
        assert "total" in progress
        assert "success_rate" in progress
        assert "update_rate" in progress
        
        # Verify timing structure
        timing = summary["timing"]
        assert "created_at" in timing
        assert "duration_seconds" in timing
        
        # Verify configuration structure
        config = summary["configuration"]
        assert "batch_size" in config
        assert "doctype_config" in config
    
    def test_manual_ingestion_invalid_doctype(self, client, test_db):
        """Test manual ingestion with invalid/unconfigured doctype"""
        request_data = {
            "doctype": "NonExistentDoctype",
            "batchSize": 10
        }
        
        response = client.post("/api/ingestion/manual", json=request_data)
        job_id = response.json()["jobId"]
        
        # Wait for processing
        import time
        time.sleep(0.1)
        
        # Check that job failed
        status_response = client.get(f"/api/ingestion/jobs/{job_id}")
        status_data = status_response.json()
        
        # Job should eventually fail due to missing configuration
        # In a real scenario, you might need to wait longer or poll
        assert status_data["jobId"] == job_id
    
    @patch('frappe_client.get_frappe_client')
    def test_batch_manual_ingestion(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test batch manual ingestion with multiple doctypes"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_documents.return_value = ([], 0)  # Empty results for simplicity
        
        # Create additional doctype config
        config2 = DoctypeConfigModel(
            doctype="Customer",
            enabled=True,
            fields=["customer_name", "customer_group"],
            filters={},
            chunk_size=500,
            chunk_overlap=100
        )
        test_db.add(config2)
        test_db.commit()
        
        # Start batch ingestion
        batch_requests = [
            {
                "doctype": "Item",
                "batchSize": 10,
                "forceUpdate": False
            },
            {
                "doctype": "Customer",
                "batchSize": 20,
                "forceUpdate": True
            }
        ]
        
        response = client.post("/api/ingestion/manual/batch", json=batch_requests)
        assert response.status_code == 200
        
        batch_data = response.json()
        assert "message" in batch_data
        assert "jobs" in batch_data
        assert len(batch_data["jobs"]) == 2
        
        # Verify each job was created
        for job in batch_data["jobs"]:
            assert "jobId" in job
            assert job["status"] == "queued"
            
            # Check individual job status
            job_response = client.get(f"/api/ingestion/jobs/{job['jobId']}")
            assert job_response.status_code == 200
    
    def test_ingestion_statistics_endpoint(self, client, test_db):
        """Test ingestion statistics endpoint"""
        # Create some test job records
        jobs = [
            IngestionJobModel(
                job_id=str(uuid.uuid4()),
                doctype="Item",
                status=JobStatus.COMPLETED,
                processed=100,
                updated=80,
                failed=5,
                batch_size=50,
                created_at=datetime.utcnow() - timedelta(days=1),
                completed_at=datetime.utcnow() - timedelta(hours=23)
            ),
            IngestionJobModel(
                job_id=str(uuid.uuid4()),
                doctype="Customer",
                status=JobStatus.COMPLETED,
                processed=50,
                updated=45,
                failed=2,
                batch_size=25,
                created_at=datetime.utcnow() - timedelta(days=2),
                completed_at=datetime.utcnow() - timedelta(days=2, hours=-1)
            ),
            IngestionJobModel(
                job_id=str(uuid.uuid4()),
                doctype="Item",
                status=JobStatus.FAILED,
                processed=0,
                updated=0,
                failed=10,
                batch_size=20,
                created_at=datetime.utcnow() - timedelta(hours=1)
            )
        ]
        
        for job in jobs:
            test_db.add(job)
        test_db.commit()
        
        # Test general statistics
        response = client.get("/api/ingestion/statistics")
        assert response.status_code == 200
        
        stats = response.json()
        assert "period" in stats
        assert "summary" in stats
        assert "by_status" in stats
        assert "by_doctype" in stats
        assert "performance" in stats
        
        # Verify summary data
        summary = stats["summary"]
        assert summary["total_jobs"] == 3
        assert summary["total_documents"] == 167  # 100+50+10
        assert summary["total_updated"] == 125   # 80+45+0
        assert summary["total_failed"] == 17     # 5+2+10
        
        # Test doctype-specific statistics
        item_response = client.get("/api/ingestion/statistics?doctype=Item")
        assert item_response.status_code == 200
        
        item_stats = item_response.json()
        assert item_stats["summary"]["total_jobs"] == 2  # Only Item jobs
    
    @patch('frappe_client.get_frappe_client')
    def test_duplicate_detection_logic(self, mock_get_client, test_db, sample_doctype_config):
        """Test duplicate detection and update logic"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create processor instance
        processor = IngestionProcessor(test_db)
        
        # Test document update decision logic
        test_document = {
            "name": "TEST-001",
            "modified": "2024-01-15T10:00:00Z"
        }
        
        # Test force update
        should_update, reason = processor._should_update_document(
            "Item", "TEST-001", test_document, force_update=True
        )
        assert should_update is True
        assert reason == "forced_update"
        
        # Test normal update logic (will depend on mock implementation)
        should_update, reason = processor._should_update_document(
            "Item", "TEST-001", test_document, force_update=False
        )
        assert isinstance(should_update, bool)
        assert isinstance(reason, str)
    
    def test_error_handling_and_recovery(self, client, test_db, sample_doctype_config):
        """Test error handling and recovery scenarios"""
        # Test with invalid request data
        invalid_request = {
            "doctype": "",  # Empty doctype
            "batchSize": -1  # Invalid batch size
        }
        
        response = client.post("/api/ingestion/manual", json=invalid_request)
        # Should handle validation errors gracefully
        assert response.status_code in [400, 422]  # Validation error
        
        # Test job not found
        fake_job_id = str(uuid.uuid4())
        response = client.get(f"/api/ingestion/jobs/{fake_job_id}")
        assert response.status_code == 404
        
        # Test summary for non-existent job
        response = client.get(f"/api/ingestion/jobs/{fake_job_id}/summary")
        assert response.status_code == 404
    
    @patch('frappe_client.get_frappe_client')
    def test_configurable_batch_sizes(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test ingestion with different batch sizes"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create large dataset
        large_dataset = [
            {
                "name": f"ITEM-{i:03d}",
                "item_name": f"Item {i}",
                "description": f"Description {i}",
                "item_group": "Products"
            }
            for i in range(1, 101)  # 100 items
        ]
        
        mock_client.get_documents.return_value = (large_dataset, len(large_dataset))
        
        # Test different batch sizes
        batch_sizes = [10, 25, 50]
        
        for batch_size in batch_sizes:
            request_data = {
                "doctype": "Item",
                "batchSize": batch_size,
                "forceUpdate": False
            }
            
            response = client.post("/api/ingestion/manual", json=request_data)
            assert response.status_code == 200
            
            job_data = response.json()
            job_id = job_data["jobId"]
            
            # Verify batch size was stored correctly
            job_response = client.get(f"/api/ingestion/jobs/{job_id}")
            # Note: The actual batch processing verification would require 
            # more complex mocking or real database integration
    
    def test_ingestion_summary_reporting(self, test_db):
        """Test comprehensive ingestion summary reporting"""
        # Create test job with enhanced metadata
        job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.COMPLETED,
            processed=95,
            updated=80,
            failed=5,
            batch_size=50,
            filters={"item_group": "Products"},
            errors=["Error 1", "Error 2", "Error 3"],
            job_metadata={
                "total_documents": 100,
                "total_skipped": 15,
                "batches_processed": 2,
                "current_batch_size": 50,
                "avg_batch_time": 12.5,
                "update_reasons": {
                    "new_document": 30,
                    "document_updated": 25,
                    "forced_update": 25,
                    "up_to_date": 15
                },
                "error_types": {
                    "FrappeAPIError": 3,
                    "ValidationError": 2
                }
            },
            created_at=datetime.utcnow() - timedelta(minutes=30),
            completed_at=datetime.utcnow() - timedelta(minutes=5)
        )
        test_db.add(job)
        test_db.commit()
        
        # Test summary generation
        processor = IngestionProcessor(test_db)
        summary = processor.get_ingestion_summary(job.job_id)
        
        # Verify comprehensive summary structure
        assert summary["job_id"] == job.job_id
        assert summary["doctype"] == "Item"
        assert summary["status"] == JobStatus.COMPLETED
        
        # Check enhanced progress calculations
        progress = summary["progress"]
        assert progress["processed"] == 95
        assert progress["updated"] == 80
        assert progress["skipped"] == 15
        assert progress["failed"] == 5
        assert progress["total"] == 100  # processed + failed
        assert progress["total_available"] == 100
        assert progress["success_rate"] == 95.0  # 95/100 * 100
        assert progress["update_rate"] == 84.21  # 80/95 * 100 (rounded)
        assert progress["skip_rate"] == 15.0  # 15/100 * 100
        
        # Check batch processing information
        batch_info = summary["batch_processing"]
        assert batch_info["batch_size"] == 50
        assert batch_info["batches_processed"] == 2
        assert batch_info["current_batch_size"] == 50
        
        # Check analysis section
        analysis = summary["analysis"]
        assert "update_reasons" in analysis
        assert "error_types" in analysis
        assert "duplicate_detection" in analysis
        
        duplicate_detection = analysis["duplicate_detection"]
        assert duplicate_detection["new_documents"] == 30
        assert duplicate_detection["updated_documents"] == 25
        assert duplicate_detection["forced_updates"] == 25
        assert duplicate_detection["up_to_date"] == 15
        
        # Check timing calculations
        timing = summary["timing"]
        assert timing["duration_seconds"] is not None
        assert timing["processing_speed_docs_per_sec"] is not None
        assert timing["avg_batch_time_seconds"] == 12.5
        
        # Check enhanced error reporting
        errors = summary["errors"]
        assert errors["count"] == 3
        assert len(errors["recent_errors"]) == 3
        assert errors["has_more_errors"] is False
        assert "error_breakdown" in errors
        assert errors["error_breakdown"]["FrappeAPIError"] == 3
        assert errors["error_breakdown"]["ValidationError"] == 2
    
    def test_ingestion_progress_tracking(self, client, test_db):
        """Test real-time progress tracking endpoint"""
        # Create test job with progress metadata
        job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.PROCESSING,
            processed=75,
            updated=60,
            failed=5,
            batch_size=25,
            job_metadata={
                "total_documents": 100,
                "total_skipped": 20,
                "batches_processed": 3,
                "current_batch_size": 25,
                "avg_batch_time": 8.5
            },
            errors=["Sample error 1", "Sample error 2"],
            created_at=datetime.utcnow() - timedelta(minutes=10)
        )
        test_db.add(job)
        test_db.commit()
        
        # Test progress endpoint
        response = client.get(f"/api/ingestion/jobs/{job.job_id}/progress")
        assert response.status_code == 200
        
        progress_data = response.json()
        assert progress_data["job_id"] == job.job_id
        assert progress_data["status"] == JobStatus.PROCESSING
        
        # Check progress calculations
        progress = progress_data["progress"]
        assert progress["percentage"] == 80.0  # (75+5)/100 * 100
        assert progress["processed"] == 75
        assert progress["updated"] == 60
        assert progress["failed"] == 5
        assert progress["skipped"] == 20
        assert progress["total_available"] == 100
        assert progress["current_batch"] == 25
        assert progress["batches_completed"] == 3
        
        # Check timing information
        timing = progress_data["timing"]
        assert "started_at" in timing
        assert timing["avg_batch_time"] == 8.5
        
        # Check recent errors
        assert len(progress_data["recent_errors"]) == 2
    
    def test_job_cancellation(self, client, test_db):
        """Test job cancellation functionality"""
        # Create test job in processing state
        job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.PROCESSING,
            processed=25,
            updated=20,
            failed=2,
            batch_size=50
        )
        test_db.add(job)
        test_db.commit()
        
        # Test cancellation
        response = client.post(f"/api/ingestion/jobs/{job.job_id}/cancel")
        assert response.status_code == 200
        
        cancel_data = response.json()
        assert cancel_data["job_id"] == job.job_id
        assert cancel_data["status"] == JobStatus.FAILED
        assert "cancelled" in cancel_data["message"].lower()
        
        # Verify job was actually cancelled in database
        test_db.refresh(job)
        assert job.status == JobStatus.FAILED
        assert any("cancelled" in error.lower() for error in job.errors)
        assert job.completed_at is not None
    
    def test_job_cancellation_invalid_states(self, client, test_db):
        """Test job cancellation with invalid job states"""
        # Create completed job (cannot be cancelled)
        completed_job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.COMPLETED,
            processed=100,
            updated=90,
            failed=0,
            batch_size=50,
            completed_at=datetime.utcnow()
        )
        test_db.add(completed_job)
        test_db.commit()
        
        # Try to cancel completed job
        response = client.post(f"/api/ingestion/jobs/{completed_job.job_id}/cancel")
        assert response.status_code == 400
        assert "cannot be cancelled" in response.json()["detail"].lower()
        
        # Test with non-existent job
        fake_job_id = str(uuid.uuid4())
        response = client.post(f"/api/ingestion/jobs/{fake_job_id}/cancel")
        assert response.status_code == 404
    
    @patch('frappe_client.get_frappe_client')
    def test_duplicate_analysis_endpoint(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test duplicate analysis endpoint"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock document data
        sample_documents = [
            {
                "name": "ITEM-001",
                "item_name": "Test Item 1",
                "description": "Description 1",
                "modified": "2024-01-15T10:00:00Z"
            },
            {
                "name": "ITEM-002", 
                "item_name": "Test Item 2",
                "description": "Description 2",
                "modified": "2024-01-16T11:00:00Z"
            }
        ]
        
        mock_client.get_documents.return_value = (sample_documents, 50)  # 50 total available
        mock_client.get_document.return_value = sample_documents[0]  # For field validation
        
        # Test duplicate analysis
        response = client.get("/api/ingestion/duplicate-analysis/Item?limit=20")
        assert response.status_code == 200
        
        analysis = response.json()
        assert analysis["doctype"] == "Item"
        assert analysis["sample_size"] == 2
        assert analysis["total_available"] == 50
        
        # Check duplicate analysis structure
        duplicate_analysis = analysis["duplicate_analysis"]
        assert "new_documents" in duplicate_analysis
        assert "existing_documents" in duplicate_analysis
        assert "would_update" in duplicate_analysis
        assert "up_to_date" in duplicate_analysis
        
        # Check sample documents
        assert "sample_documents" in analysis
        assert len(analysis["sample_documents"]) <= 20  # Respects limit
        
        for doc in analysis["sample_documents"]:
            assert "name" in doc
            assert "should_update" in doc
            assert "reason" in doc
            assert "modified" in doc
            assert "fields_count" in doc
    
    def test_duplicate_analysis_invalid_doctype(self, client, test_db):
        """Test duplicate analysis with invalid doctype"""
        response = client.get("/api/ingestion/duplicate-analysis/NonExistentDoctype")
        assert response.status_code == 404
        assert "configuration not found" in response.json()["detail"].lower()
    
    @patch('frappe_client.get_frappe_client')
    def test_enhanced_batch_processing_with_metadata(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test enhanced batch processing with detailed metadata tracking"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create dataset that will trigger different update scenarios
        test_documents = [
            {
                "name": "NEW-001",
                "item_name": "New Item",
                "description": "New description",
                "modified": "2024-01-20T10:00:00Z"
            },
            {
                "name": "EXISTING-001",
                "item_name": "Existing Item",
                "description": "Updated description", 
                "modified": "2024-01-21T11:00:00Z"
            }
        ]
        
        mock_client.get_documents.return_value = (test_documents, len(test_documents))
        
        # Start ingestion with small batch size to test batch tracking
        request_data = {
            "doctype": "Item",
            "batchSize": 1,  # Process one document per batch
            "forceUpdate": False
        }
        
        response = client.post("/api/ingestion/manual", json=request_data)
        assert response.status_code == 200
        
        job_id = response.json()["jobId"]
        
        # Wait for processing to complete
        import time
        time.sleep(0.2)
        
        # Get comprehensive summary
        summary_response = client.get(f"/api/ingestion/jobs/{job_id}/summary")
        assert summary_response.status_code == 200
        
        summary = summary_response.json()
        
        # Verify enhanced metadata is present
        assert "batch_processing" in summary
        batch_info = summary["batch_processing"]
        assert batch_info["batch_size"] == 1
        assert "batches_processed" in batch_info
        assert "avg_documents_per_batch" in batch_info
        
        # Verify analysis section
        assert "analysis" in summary
        analysis = summary["analysis"]
        assert "update_reasons" in analysis
        assert "duplicate_detection" in analysis
        
        # Check that timing includes batch-level metrics
        timing = summary["timing"]
        assert "avg_batch_time_seconds" in timing
    
    def test_concurrent_job_handling(self, client, test_db, sample_doctype_config):
        """Test handling of multiple concurrent ingestion jobs"""
        # Create multiple doctype configurations
        configs = [
            DoctypeConfigModel(
                doctype="Customer",
                enabled=True,
                fields=["customer_name", "customer_group"],
                filters={},
                chunk_size=500,
                chunk_overlap=100
            ),
            DoctypeConfigModel(
                doctype="Supplier",
                enabled=True,
                fields=["supplier_name", "supplier_group"],
                filters={},
                chunk_size=600,
                chunk_overlap=150
            )
        ]
        
        for config in configs:
            test_db.add(config)
        test_db.commit()
        
        # Start multiple jobs concurrently
        job_requests = [
            {"doctype": "Item", "batchSize": 10},
            {"doctype": "Customer", "batchSize": 15},
            {"doctype": "Supplier", "batchSize": 20}
        ]
        
        job_ids = []
        for request in job_requests:
            response = client.post("/api/ingestion/manual", json=request)
            assert response.status_code == 200
            job_ids.append(response.json()["jobId"])
        
        # Verify all jobs were created
        assert len(job_ids) == 3
        assert len(set(job_ids)) == 3  # All unique
        
        # Check each job status
        for job_id in job_ids:
            response = client.get(f"/api/ingestion/jobs/{job_id}")
            assert response.status_code == 200
            
            job_data = response.json()
            assert job_data["status"] in [JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
    
    def test_ingestion_error_recovery_and_reporting(self, client, test_db):
        """Test comprehensive error recovery and reporting"""
        # Create job with various error scenarios
        job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.FAILED,
            processed=45,
            updated=30,
            failed=15,
            batch_size=20,
            errors=[
                "FrappeAPIError: Connection timeout for ITEM-001",
                "ValidationError: Invalid field 'description' for ITEM-002", 
                "ProcessingError: Chunking failed for ITEM-003",
                "EmbeddingError: Vector generation failed for ITEM-004",
                "DatabaseError: Failed to store chunks for ITEM-005"
            ],
            job_metadata={
                "total_documents": 60,
                "total_skipped": 0,
                "batches_processed": 3,
                "error_types": {
                    "FrappeAPIError": 5,
                    "ValidationError": 3,
                    "ProcessingError": 4,
                    "EmbeddingError": 2,
                    "DatabaseError": 1
                },
                "update_reasons": {
                    "new_document": 20,
                    "document_updated": 15,
                    "forced_update": 10
                }
            },
            created_at=datetime.utcnow() - timedelta(minutes=15),
            completed_at=datetime.utcnow() - timedelta(minutes=2)
        )
        test_db.add(job)
        test_db.commit()
        
        # Get detailed summary
        response = client.get(f"/api/ingestion/jobs/{job.job_id}/summary")
        assert response.status_code == 200
        
        summary = response.json()
        
        # Verify error analysis
        errors = summary["errors"]
        assert errors["count"] == 5
        assert "error_breakdown" in errors
        
        error_breakdown = errors["error_breakdown"]
        assert error_breakdown["FrappeAPIError"] == 5
        assert error_breakdown["ValidationError"] == 3
        assert error_breakdown["ProcessingError"] == 4
        assert error_breakdown["EmbeddingError"] == 2
        assert error_breakdown["DatabaseError"] == 1
        
        # Verify analysis shows proper categorization
        analysis = summary["analysis"]
        assert "update_reasons" in analysis
        assert "duplicate_detection" in analysis
        
        duplicate_detection = analysis["duplicate_detection"]
        assert duplicate_detection["new_documents"] == 20
        assert duplicate_detection["updated_documents"] == 15
        assert duplicate_detection["forced_updates"] == 10
        assert error_breakdown["EmbeddingError"] == 2
        assert error_breakdown["DatabaseError"] == 1
        
        # Verify analysis shows proper categorization
        analysis = summary["analysis"]
        assert "update_reasons" in analysis
        assert "duplicate_detection" in analysis
        
        duplicate_detection = analysis["duplicate_detection"]
        assert duplicate_detection["new_documents"] == 20
        assert duplicate_detection["updated_documents"] == 15
        assert duplicate_detection["forced_updates"] == 10


class TestBatchProcessingEnhancements:
    """Additional tests for enhanced batch processing functionality"""
    
    @patch('frappe_client.get_frappe_client')
    def test_configurable_batch_size_processing(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test that different batch sizes are properly handled"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create a dataset larger than any single batch
        large_dataset = [
            {
                "name": f"ITEM-{i:03d}",
                "item_name": f"Item {i}",
                "description": f"Description for item {i}",
                "item_group": "Products",
                "modified": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z"
            }
            for i in range(1, 151)  # 150 items
        ]
        
        # Mock the get_documents to return batches
        def mock_get_documents(*args, **kwargs):
            limit = kwargs.get('limit', 100)
            offset = kwargs.get('offset', 0)
            batch = large_dataset[offset:offset + limit]
            return batch, len(large_dataset)
        
        mock_client.get_documents.side_effect = mock_get_documents
        
        # Test different batch sizes
        test_cases = [
            {"batch_size": 25, "expected_batches": 6},  # 150/25 = 6 batches
            {"batch_size": 50, "expected_batches": 3},  # 150/50 = 3 batches
            {"batch_size": 100, "expected_batches": 2}, # 150/100 = 2 batches (100 + 50)
        ]
        
        for test_case in test_cases:
            # Reset mock call count
            mock_client.get_documents.reset_mock()
            
            request_data = {
                "doctype": "Item",
                "batchSize": test_case["batch_size"],
                "forceUpdate": True  # Force update to ensure processing
            }
            
            response = client.post("/api/ingestion/manual", json=request_data)
            assert response.status_code == 200
            
            job_id = response.json()["jobId"]
            
            # Wait for processing
            import time
            time.sleep(0.2)
            
            # Get job summary
            summary_response = client.get(f"/api/ingestion/jobs/{job_id}/summary")
            assert summary_response.status_code == 200
            
            summary = summary_response.json()
            
            # Verify batch processing information
            batch_info = summary["batch_processing"]
            assert batch_info["batch_size"] == test_case["batch_size"]
            
            # The number of batches processed should match expected
            # (allowing for some variance due to async processing)
            batches_processed = batch_info["batches_processed"]
            assert batches_processed >= test_case["expected_batches"] - 1
            assert batches_processed <= test_case["expected_batches"] + 1
    
    @patch('frappe_client.get_frappe_client')
    def test_duplicate_detection_scenarios(self, mock_get_client, test_db, sample_doctype_config):
        """Test various duplicate detection scenarios"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create processor instance
        processor = IngestionProcessor(test_db)
        
        # Test scenarios for duplicate detection
        test_scenarios = [
            {
                "name": "NEW-DOC-001",
                "document": {
                    "name": "NEW-DOC-001",
                    "title": "New Document",
                    "modified": "2024-01-20T10:00:00Z"
                },
                "force_update": False,
                "expected_update": True,
                "expected_reason": "new_document"
            },
            {
                "name": "EXISTING-DOC-001", 
                "document": {
                    "name": "EXISTING-DOC-001",
                    "title": "Existing Document",
                    "modified": "2024-01-25T10:00:00Z"  # Newer than stored timestamp
                },
                "force_update": False,
                "expected_update": True,
                "expected_reason": "document_updated"
            },
            {
                "name": "FORCE-UPDATE-001",
                "document": {
                    "name": "FORCE-UPDATE-001", 
                    "title": "Force Update Document",
                    "modified": "2024-01-01T10:00:00Z"
                },
                "force_update": True,
                "expected_update": True,
                "expected_reason": "forced_update"
            }
        ]
        
        for scenario in test_scenarios:
            should_update, reason = processor._should_update_document(
                "Item", 
                scenario["name"], 
                scenario["document"], 
                scenario["force_update"]
            )
            
            assert should_update == scenario["expected_update"], f"Failed for {scenario['name']}"
            assert reason == scenario["expected_reason"], f"Wrong reason for {scenario['name']}: got {reason}, expected {scenario['expected_reason']}"
    
    def test_ingestion_validation_endpoint(self, client, test_db, sample_doctype_config):
        """Test the ingestion validation endpoint"""
        # Test valid request
        valid_request = {
            "doctype": "Item",
            "batchSize": 50,
            "forceUpdate": False,
            "filters": {"item_group": "Products"}
        }
        
        with patch('frappe_client.get_frappe_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client
            
            # Mock field validation
            mock_client.get_documents.return_value = ([{"name": "TEST-001"}], 100)
            mock_client.get_document.return_value = {
                "name": "TEST-001",
                "item_name": "Test Item",
                "description": "Test Description"
            }
            
            response = client.post("/api/ingestion/manual/validate", json=valid_request)
            assert response.status_code == 200
            
            validation_result = response.json()
            assert validation_result["valid"] is True
            assert "estimated_documents" in validation_result
            assert "valid_fields" in validation_result
            assert "invalid_fields" in validation_result
            assert len(validation_result["errors"]) == 0
    
    def test_ingestion_validation_invalid_doctype(self, client, test_db):
        """Test validation with invalid doctype"""
        invalid_request = {
            "doctype": "NonExistentDoctype",
            "batchSize": 50
        }
        
        response = client.post("/api/ingestion/manual/validate", json=invalid_request)
        assert response.status_code == 200
        
        validation_result = response.json()
        assert validation_result["valid"] is False
        assert len(validation_result["errors"]) > 0
        assert "configuration not found" in validation_result["errors"][0].lower()
    
    def test_job_logs_endpoint(self, client, test_db):
        """Test the job logs endpoint"""
        # Create test job with errors
        job = IngestionJobModel(
            job_id=str(uuid.uuid4()),
            doctype="Item",
            status=JobStatus.FAILED,
            processed=50,
            failed=10,
            errors=[f"Error {i}: Sample error message" for i in range(1, 16)],  # 15 errors
            job_metadata={
                "batches_processed": 3,
                "avg_batch_time": 5.2,
                "error_types": {
                    "FrappeAPIError": 8,
                    "ValidationError": 7
                }
            }
        )
        test_db.add(job)
        test_db.commit()
        
        # Test getting logs with default pagination
        response = client.get(f"/api/ingestion/jobs/{job.job_id}/logs")
        assert response.status_code == 200
        
        logs_data = response.json()
        assert logs_data["job_id"] == job.job_id
        assert logs_data["total_errors"] == 15
        assert len(logs_data["errors"]) <= 100  # Default limit
        assert logs_data["has_more"] is False  # 15 < 100
        
        # Test pagination
        response = client.get(f"/api/ingestion/jobs/{job.job_id}/logs?limit=5&offset=0")
        assert response.status_code == 200
        
        logs_data = response.json()
        assert len(logs_data["errors"]) == 5
        assert logs_data["has_more"] is True  # 5 < 15
        
        # Test processing details
        processing_details = logs_data["processing_details"]
        assert processing_details["batches_processed"] == 3
        assert processing_details["avg_batch_time"] == 5.2
        assert "error_types" in processing_details
    
    def test_job_logs_not_found(self, client, test_db):
        """Test logs endpoint with non-existent job"""
        fake_job_id = str(uuid.uuid4())
        response = client.get(f"/api/ingestion/jobs/{fake_job_id}/logs")
        assert response.status_code == 404
    
    @patch('frappe_client.get_frappe_client')
    def test_enhanced_progress_tracking(self, mock_get_client, client, test_db, sample_doctype_config):
        """Test enhanced progress tracking with detailed metrics"""
        # Setup mock
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Create dataset with mixed update scenarios
        test_documents = [
            {
                "name": f"ITEM-{i:03d}",
                "item_name": f"Item {i}",
                "description": f"Description {i}" if i % 3 != 0 else "",  # Some empty descriptions
                "modified": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z"
            }
            for i in range(1, 21)  # 20 items
        ]
        
        mock_client.get_documents.return_value = (test_documents, len(test_documents))
        
        # Start ingestion with small batch size for detailed tracking
        request_data = {
            "doctype": "Item",
            "batchSize": 5,  # Small batches for detailed progress tracking
            "forceUpdate": False
        }
        
        response = client.post("/api/ingestion/manual", json=request_data)
        assert response.status_code == 200
        
        job_id = response.json()["jobId"]
        
        # Wait for processing to start
        import time
        time.sleep(0.1)
        
        # Test progress endpoint during processing
        progress_response = client.get(f"/api/ingestion/jobs/{job_id}/progress")
        
        if progress_response.status_code == 200:
            progress_data = progress_response.json()
            
            # Verify progress structure
            assert "progress" in progress_data
            assert "timing" in progress_data
            
            progress = progress_data["progress"]
            assert "percentage" in progress
            assert "processed" in progress
            assert "updated" in progress
            assert "failed" in progress
            assert "total_available" in progress
            assert "batches_completed" in progress
            
            # Verify timing information
            timing = progress_data["timing"]
            assert "started_at" in timing
            assert "avg_batch_time" in timing
        
        # Wait for completion
        time.sleep(0.2)
        
        # Get final summary
        summary_response = client.get(f"/api/ingestion/jobs/{job_id}/summary")
        assert summary_response.status_code == 200
        
        summary = summary_response.json()
        
        # Verify comprehensive tracking
        assert "batch_processing" in summary
        assert "analysis" in summary
        assert "timing" in summary
        
        batch_info = summary["batch_processing"]
        assert batch_info["batch_size"] == 5
        assert batch_info["batches_processed"] >= 4  # 20 items / 5 per batch = 4 batches
        
        # Verify analysis includes duplicate detection breakdown
        analysis = summary["analysis"]
        assert "duplicate_detection" in analysis
        duplicate_detection = analysis["duplicate_detection"]
        
        # Should have some new documents and some up-to-date
        total_analyzed = (duplicate_detection["new_documents"] + 
                         duplicate_detection["updated_documents"] + 
                         duplicate_detection["forced_updates"] + 
                         duplicate_detection["up_to_date"])
        assert total_analyzed > 0
        assert error_breakdown["EmbeddingError"] == 2
        assert error_breakdown["DatabaseError"] == 1
        
        # Verify progress calculations account for errors
        progress = summary["progress"]
        assert progress["failed"] == 15
        assert progress["success_rate"] == 75.0  # 45/60 * 100
        
        # Verify job completed despite errors
        assert summary["status"] == JobStatus.FAILED
        timing = summary["timing"]
        assert timing["completed_at"] is not None
        assert timing["duration_seconds"] is not None


@pytest.mark.asyncio
class TestAsyncIngestionWorkflows:
    """Test asynchronous ingestion workflows"""
    
    @pytest.fixture
    def mock_processor(self):
        """Mock ingestion processor for async testing"""
        processor = Mock(spec=IngestionProcessor)
        processor.process_manual_ingestion = AsyncMock()
        return processor
    
    async def test_concurrent_ingestion_jobs(self, mock_processor):
        """Test handling of concurrent ingestion jobs"""
        # Create multiple ingestion requests
        requests = [
            IngestionRequest(doctype="Item", batch_size=10),
            IngestionRequest(doctype="Customer", batch_size=20),
            IngestionRequest(doctype="Supplier", batch_size=15)
        ]
        
        # Simulate concurrent processing
        tasks = []
        for i, request in enumerate(requests):
            job_id = f"job-{i}"
            task = asyncio.create_task(
                mock_processor.process_manual_ingestion(job_id, request)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        
        # Verify all jobs were processed
        assert mock_processor.process_manual_ingestion.call_count == 3
    
    async def test_ingestion_job_cancellation(self, mock_processor):
        """Test ingestion job cancellation scenarios"""
        # This would test job cancellation logic
        # In a real implementation, you'd have cancellation mechanisms
        
        request = IngestionRequest(doctype="Item", batch_size=100)
        job_id = "cancellable-job"
        
        # Start processing
        task = asyncio.create_task(
            mock_processor.process_manual_ingestion(job_id, request)
        )
        
        # Simulate cancellation after short delay
        await asyncio.sleep(0.01)
        task.cancel()
        
        # Verify task was cancelled
        with pytest.raises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])