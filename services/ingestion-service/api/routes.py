"""
API routes for the ingestion service
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid
import logging
from datetime import datetime

from database import get_db
from frappe_client import get_frappe_client, FrappeAPIError
from models.database_models import DoctypeConfigModel, IngestionJobModel
from services.document_fetcher import DocumentFetcher
from services.ingestion_processor import IngestionProcessor

# Import shared models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
from shared.models.config import DoctypeConfig
from shared.models.ingestion import IngestionRequest, IngestionResponse
from shared.models.base import JobStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/test-frappe")
async def test_frappe_connection():
    """Test Frappe API connection"""
    try:
        client = get_frappe_client()
        success = client.test_connection()
        return {"success": success, "message": "Connection test completed"}
    except Exception as e:
        logger.error(f"Frappe connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctypes/{doctype}/test")
async def test_doctype_fetch(doctype: str, limit: int = 5):
    """Test fetching documents for a specific doctype"""
    try:
        client = get_frappe_client()
        documents, total = client.get_documents(
            doctype=doctype,
            limit=limit,
            fields=["name", "creation", "modified"]
        )
        
        return {
            "success": True,
            "doctype": doctype,
            "total_available": total,
            "fetched": len(documents),
            "sample_documents": documents
        }
        
    except FrappeAPIError as e:
        logger.error(f"Failed to fetch {doctype} documents: {e}")
        raise HTTPException(status_code=400, detail=f"Frappe API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error testing {doctype}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctypes/{doctype}/document/{docname}")
async def get_document(doctype: str, docname: str, fields: str = None):
    """Fetch a specific document with optional field selection"""
    try:
        client = get_frappe_client()
        field_list = fields.split(',') if fields else None
        
        document = client.get_document(doctype, docname, field_list)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "doctype": doctype,
            "docname": docname,
            "document": document
        }
        
    except FrappeAPIError as e:
        logger.error(f"Failed to fetch document {doctype}/{docname}: {e}")
        raise HTTPException(status_code=400, detail=f"Frappe API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/doctypes/{doctype}/config")
async def create_doctype_config(
    doctype: str, 
    config: DoctypeConfig, 
    db: Session = Depends(get_db)
):
    """Create or update doctype configuration"""
    try:
        # Check if config already exists
        existing = db.query(DoctypeConfigModel).filter(
            DoctypeConfigModel.doctype == doctype
        ).first()
        
        if existing:
            # Update existing config
            existing.enabled = config.enabled
            existing.fields = config.fields
            existing.filters = config.filters
            existing.chunk_size = config.chunk_size
            existing.chunk_overlap = config.chunk_overlap
        else:
            # Create new config
            db_config = DoctypeConfigModel(
                doctype=doctype,
                enabled=config.enabled,
                fields=config.fields,
                filters=config.filters,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap
            )
            db.add(db_config)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Configuration for {doctype} {'updated' if existing else 'created'}"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save config for {doctype}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctypes/{doctype}/config")
async def get_doctype_config(doctype: str, db: Session = Depends(get_db)):
    """Get doctype configuration"""
    config = db.query(DoctypeConfigModel).filter(
        DoctypeConfigModel.doctype == doctype
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return DoctypeConfig(
        doctype=config.doctype,
        enabled=config.enabled,
        fields=config.fields,
        filters=config.filters,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        last_sync=config.last_sync
    )


@router.get("/configs")
async def list_doctype_configs(db: Session = Depends(get_db)):
    """List all doctype configurations"""
    configs = db.query(DoctypeConfigModel).all()
    
    return [
        DoctypeConfig(
            doctype=config.doctype,
            enabled=config.enabled,
            fields=config.fields,
            filters=config.filters,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            last_sync=config.last_sync
        )
        for config in configs
    ]


@router.post("/ingestion/manual")
async def start_manual_ingestion(
    request: IngestionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start manual document ingestion"""
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job record
        job = IngestionJobModel(
            job_id=job_id,
            doctype=request.doctype,
            status=JobStatus.QUEUED,
            filters=request.filters or {},
            batch_size=request.batch_size
        )
        db.add(job)
        db.commit()
        
        # Start background processing
        processor = IngestionProcessor(db)
        background_tasks.add_task(
            processor.process_manual_ingestion,
            job_id,
            request
        )
        
        return IngestionResponse(
            job_id=job_id,
            status=JobStatus.QUEUED
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to start manual ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion/jobs/{job_id}")
async def get_ingestion_job(job_id: str, db: Session = Depends(get_db)):
    """Get ingestion job status"""
    job = db.query(IngestionJobModel).filter(
        IngestionJobModel.job_id == job_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return IngestionResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        processed=job.processed,
        updated=job.updated,
        failed=job.failed,
        errors=job.errors
    )


@router.get("/ingestion/jobs")
async def list_ingestion_jobs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List ingestion jobs"""
    jobs = db.query(IngestionJobModel).offset(offset).limit(limit).all()
    
    return [
        IngestionResponse(
            job_id=job.job_id,
            status=JobStatus(job.status),
            processed=job.processed,
            updated=job.updated,
            failed=job.failed,
            errors=job.errors
        )
        for job in jobs
    ]


@router.get("/ingestion/jobs/{job_id}/summary")
async def get_ingestion_job_summary(job_id: str, db: Session = Depends(get_db)):
    """Get detailed summary of ingestion job"""
    processor = IngestionProcessor(db)
    summary = processor.get_ingestion_summary(job_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    
    return summary


@router.get("/ingestion/statistics")
async def get_ingestion_statistics(
    doctype: str = None,
    limit_days: int = 30,
    db: Session = Depends(get_db)
):
    """Get ingestion statistics for analysis"""
    processor = IngestionProcessor(db)
    return processor.get_ingestion_statistics(doctype, limit_days)


@router.post("/ingestion/manual/batch")
async def start_batch_manual_ingestion(
    requests: List[IngestionRequest],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start multiple manual ingestion jobs in batch"""
    try:
        job_responses = []
        
        for request in requests:
            # Generate job ID
            job_id = str(uuid.uuid4())
            
            # Create job record
            job = IngestionJobModel(
                job_id=job_id,
                doctype=request.doctype,
                status=JobStatus.QUEUED,
                filters=request.filters or {},
                batch_size=request.batch_size
            )
            db.add(job)
            
            # Add to response list
            job_responses.append(IngestionResponse(
                job_id=job_id,
                status=JobStatus.QUEUED
            ))
        
        db.commit()
        
        # Start background processing for all jobs
        processor = IngestionProcessor(db)
        for i, request in enumerate(requests):
            background_tasks.add_task(
                processor.process_manual_ingestion,
                job_responses[i].job_id,
                request
            )
        
        return {
            "message": f"Started {len(requests)} ingestion jobs",
            "jobs": job_responses
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to start batch manual ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion/jobs/{job_id}/progress")
async def get_ingestion_progress(job_id: str, db: Session = Depends(get_db)):
    """Get real-time progress of ingestion job"""
    job = db.query(IngestionJobModel).filter(
        IngestionJobModel.job_id == job_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Calculate progress metrics
    metadata = job.job_metadata or {}
    total_available = metadata.get('total_documents', job.processed + job.failed)
    total_processed = job.processed + job.failed
    
    progress_percentage = (total_processed / total_available * 100) if total_available > 0 else 0
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": {
            "percentage": round(progress_percentage, 2),
            "processed": job.processed,
            "updated": job.updated,
            "failed": job.failed,
            "skipped": metadata.get('total_skipped', 0),
            "total_available": total_available,
            "current_batch": metadata.get('current_batch_size', 0),
            "batches_completed": metadata.get('batches_processed', 0)
        },
        "timing": {
            "started_at": job.created_at.isoformat() if job.created_at else None,
            "estimated_completion": None,  # Could calculate based on current speed
            "avg_batch_time": metadata.get('avg_batch_time', 0)
        },
        "recent_errors": job.errors[-5:] if job.errors else []
    }


@router.post("/ingestion/jobs/{job_id}/cancel")
async def cancel_ingestion_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running ingestion job"""
    job = db.query(IngestionJobModel).filter(
        IngestionJobModel.job_id == job_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.QUEUED, JobStatus.PROCESSING]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled in current status")
    
    # Update job status to failed with cancellation message
    job.status = JobStatus.FAILED
    if not job.errors:
        job.errors = []
    job.errors.append("Job cancelled by user")
    job.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Job cancelled successfully",
        "job_id": job_id,
        "status": job.status
    }


@router.post("/ingestion/manual/validate")
async def validate_ingestion_request(
    request: IngestionRequest,
    db: Session = Depends(get_db)
):
    """Validate ingestion request before starting job"""
    try:
        # Check if doctype configuration exists
        config = db.query(DoctypeConfigModel).filter(
            DoctypeConfigModel.doctype == request.doctype
        ).first()
        
        if not config:
            return {
                "valid": False,
                "errors": [f"No configuration found for doctype {request.doctype}"],
                "warnings": []
            }
        
        if not config.enabled:
            return {
                "valid": False,
                "errors": [f"Doctype {request.doctype} is disabled"],
                "warnings": []
            }
        
        # Validate fields exist
        fetcher = DocumentFetcher()
        valid_fields, invalid_fields = fetcher.validate_doctype_fields(
            request.doctype, config.fields
        )
        
        errors = []
        warnings = []
        
        if invalid_fields:
            warnings.append(f"Invalid fields will be ignored: {invalid_fields}")
        
        if not valid_fields:
            errors.append(f"No valid fields found for doctype {request.doctype}")
        
        # Check document count
        combined_filters = {**config.filters, **(request.filters or {})}
        total_documents = fetcher.get_document_count(request.doctype, combined_filters)
        
        if total_documents == 0:
            warnings.append("No documents found matching the specified filters")
        elif total_documents > 10000:
            warnings.append(f"Large dataset detected ({total_documents} documents). Consider using filters to reduce scope.")
        
        # Validate batch size
        if request.batch_size > 1000:
            warnings.append("Large batch size may impact performance. Consider using smaller batches.")
        elif request.batch_size < 10:
            warnings.append("Very small batch size may slow down processing.")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "estimated_documents": total_documents,
            "valid_fields": valid_fields,
            "invalid_fields": invalid_fields
        }
        
    except Exception as e:
        logger.error(f"Failed to validate ingestion request: {e}")
        return {
            "valid": False,
            "errors": [f"Validation failed: {e}"],
            "warnings": []
        }


@router.get("/ingestion/jobs/{job_id}/logs")
async def get_ingestion_job_logs(
    job_id: str, 
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get detailed logs for an ingestion job"""
    job = db.query(IngestionJobModel).filter(
        IngestionJobModel.job_id == job_id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get errors with pagination
    errors = job.errors or []
    total_errors = len(errors)
    paginated_errors = errors[offset:offset + limit]
    
    # Get processing metadata
    metadata = job.job_metadata or {}
    
    return {
        "job_id": job.job_id,
        "total_errors": total_errors,
        "errors": paginated_errors,
        "has_more": offset + limit < total_errors,
        "processing_details": {
            "batches_processed": metadata.get('batches_processed', 0),
            "avg_batch_time": metadata.get('avg_batch_time', 0),
            "update_reasons": metadata.get('update_reasons', {}),
            "error_types": metadata.get('error_types', {}),
            "last_batch_size": metadata.get('current_batch_size', 0)
        }
    }


@router.get("/ingestion/duplicate-analysis/{doctype}")
async def analyze_duplicates(
    doctype: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Analyze potential duplicates for a doctype before ingestion"""
    try:
        # Get doctype configuration
        config = db.query(DoctypeConfigModel).filter(
            DoctypeConfigModel.doctype == doctype
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Doctype configuration not found")
        
        # Get document fetcher and analyze documents
        fetcher = DocumentFetcher()
        processor = IngestionProcessor(db)
        
        # Fetch a sample of documents
        batch_result = fetcher.fetch_documents_batch(
            doctype=doctype,
            fields=config.fields,
            filters=config.filters,
            limit=limit
        )
        
        analysis = {
            "doctype": doctype,
            "sample_size": len(batch_result.successful),
            "total_available": fetcher.get_document_count(doctype, config.filters),
            "duplicate_analysis": {
                "new_documents": 0,
                "existing_documents": 0,
                "would_update": 0,
                "up_to_date": 0
            },
            "sample_documents": []
        }
        
        # Analyze each document for duplicate status
        for document in batch_result.successful[:20]:  # Analyze first 20 for detailed view
            should_update, reason = processor._should_update_document(
                doctype, document['name'], document, force_update=False
            )
            
            doc_analysis = {
                "name": document['name'],
                "should_update": should_update,
                "reason": reason,
                "modified": document.get('modified'),
                "fields_count": len([k for k, v in document.items() if v and str(v).strip()])
            }
            
            analysis["sample_documents"].append(doc_analysis)
            
            # Update counters
            if reason == "new_document":
                analysis["duplicate_analysis"]["new_documents"] += 1
            elif reason == "up_to_date":
                analysis["duplicate_analysis"]["up_to_date"] += 1
            elif should_update:
                analysis["duplicate_analysis"]["would_update"] += 1
            else:
                analysis["duplicate_analysis"]["existing_documents"] += 1
        
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to analyze duplicates for {doctype}: {e}")
        raise HTTPException(status_code=500, detail=str(e))