"""
Ingestion processor service for handling document ingestion workflows
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from models.database_models import DoctypeConfigModel, IngestionJobModel
from services.document_fetcher import DocumentFetcher, BatchFetchResult

# Import shared models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
from shared.models.ingestion import IngestionRequest
from shared.models.base import JobStatus

logger = logging.getLogger(__name__)


class IngestionProcessor:
    """Service for processing document ingestion jobs"""
    
    def __init__(self, db_session: Session, document_fetcher: DocumentFetcher = None):
        """Initialize ingestion processor
        
        Args:
            db_session: Database session
            document_fetcher: Optional document fetcher instance
        """
        self.db = db_session
        self.document_fetcher = document_fetcher or DocumentFetcher()
    
    async def process_manual_ingestion(self, job_id: str, request: IngestionRequest):
        """Process manual ingestion request
        
        Args:
            job_id: Unique job identifier
            request: Ingestion request parameters
        """
        try:
            logger.info(f"Starting manual ingestion job {job_id} for {request.doctype}")
            
            # Update job status to processing
            job = self.db.query(IngestionJobModel).filter(
                IngestionJobModel.job_id == job_id
            ).first()
            
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            job.status = JobStatus.PROCESSING
            self.db.commit()
            
            # Get doctype configuration
            config = self.db.query(DoctypeConfigModel).filter(
                DoctypeConfigModel.doctype == request.doctype
            ).first()
            
            if not config:
                error_msg = f"No configuration found for doctype {request.doctype}"
                logger.error(error_msg)
                job.status = JobStatus.FAILED
                job.errors = [error_msg]
                self.db.commit()
                return
            
            if not config.enabled:
                error_msg = f"Doctype {request.doctype} is disabled"
                logger.error(error_msg)
                job.status = JobStatus.FAILED
                job.errors = [error_msg]
                self.db.commit()
                return
            
            # Merge filters from config and request
            combined_filters = {**config.filters, **(request.filters or {})}
            
            # Validate fields exist
            valid_fields, invalid_fields = self.document_fetcher.validate_doctype_fields(
                request.doctype, config.fields
            )
            
            if invalid_fields:
                logger.warning(f"Invalid fields for {request.doctype}: {invalid_fields}")
            
            if not valid_fields:
                error_msg = f"No valid fields found for doctype {request.doctype}"
                logger.error(error_msg)
                job.status = JobStatus.FAILED
                job.errors = [error_msg]
                self.db.commit()
                return
            
            # Get total document count for progress tracking
            total_documents = self.document_fetcher.get_document_count(request.doctype, combined_filters)
            logger.info(f"Starting ingestion of {total_documents} documents for {request.doctype}")
            
            # Process documents in batches with enhanced tracking
            total_processed = 0
            total_updated = 0
            total_skipped = 0
            total_failed = 0
            all_errors = []
            batch_count = 0
            
            # Track processing statistics
            processing_stats = {
                'batches_processed': 0,
                'documents_per_batch': [],
                'processing_times': [],
                'update_reasons': {},
                'error_types': {}
            }
            
            for batch_result in self.document_fetcher.fetch_documents_generator(
                doctype=request.doctype,
                fields=valid_fields,
                filters=combined_filters,
                batch_size=request.batch_size
            ):
                batch_start_time = datetime.utcnow()
                batch_count += 1
                batch_processed = 0
                batch_updated = 0
                batch_skipped = 0
                batch_failed = 0
                
                logger.info(f"Processing batch {batch_count} with {len(batch_result.successful)} documents")
                
                # Process each successful document in the batch
                for document in batch_result.successful:
                    try:
                        # Check if document should be updated
                        should_update, update_reason = self._should_update_document(
                            request.doctype, document['name'], document, request.force_update
                        )
                        
                        if should_update:
                            # Here we would normally send to chunking/embedding services
                            # For now, we'll simulate processing time and success
                            await self._process_document_for_embedding(
                                doctype=request.doctype,
                                document=document,
                                config=config
                            )
                            
                            batch_updated += 1
                            total_updated += 1
                            
                            # Track update reasons
                            if update_reason not in processing_stats['update_reasons']:
                                processing_stats['update_reasons'][update_reason] = 0
                            processing_stats['update_reasons'][update_reason] += 1
                            
                            logger.debug(f"Document {document['name']} processed: {update_reason}")
                        else:
                            batch_skipped += 1
                            total_skipped += 1
                            logger.debug(f"Document {document['name']} skipped: {update_reason}")
                        
                        batch_processed += 1
                        total_processed += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to process {document.get('name', 'unknown')}: {e}"
                        logger.error(error_msg)
                        all_errors.append(error_msg)
                        batch_failed += 1
                        total_failed += 1
                        
                        # Track error types
                        error_type = type(e).__name__
                        if error_type not in processing_stats['error_types']:
                            processing_stats['error_types'][error_type] = 0
                        processing_stats['error_types'][error_type] += 1
                
                # Add batch errors from document fetcher
                for failed_result in batch_result.failed:
                    error_msg = f"Failed to fetch {failed_result.docname}: {failed_result.error}"
                    all_errors.append(error_msg)
                    batch_failed += 1
                    total_failed += 1
                
                all_errors.extend(batch_result.errors)
                
                # Calculate batch processing time
                batch_end_time = datetime.utcnow()
                batch_duration = (batch_end_time - batch_start_time).total_seconds()
                
                # Update processing statistics
                processing_stats['batches_processed'] += 1
                processing_stats['documents_per_batch'].append(batch_processed)
                processing_stats['processing_times'].append(batch_duration)
                
                # Update job progress with detailed information
                job.processed = total_processed
                job.updated = total_updated
                job.failed = total_failed
                job.errors = all_errors[-100:]  # Keep last 100 errors
                
                # Store processing statistics in job metadata
                if job.job_metadata is None:
                    job.job_metadata = {}
                
                job.job_metadata.update({
                    'total_documents': total_documents,
                    'total_skipped': total_skipped,
                    'batches_processed': processing_stats['batches_processed'],
                    'current_batch_size': batch_processed,
                    'avg_batch_time': sum(processing_stats['processing_times']) / len(processing_stats['processing_times']) if processing_stats['processing_times'] else 0,
                    'update_reasons': processing_stats['update_reasons'],
                    'error_types': processing_stats['error_types']
                })
                
                self.db.commit()
                
                # Calculate progress percentage
                progress_pct = (total_processed / total_documents * 100) if total_documents > 0 else 0
                
                logger.info(f"Job {job_id} batch {batch_count} completed: "
                          f"{batch_processed} processed ({batch_updated} updated, {batch_skipped} skipped, {batch_failed} failed) "
                          f"in {batch_duration:.2f}s. Overall progress: {progress_pct:.1f}%")
            
            # Mark job as completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            # Update config last sync time
            config.last_sync = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Completed manual ingestion job {job_id}: "
                       f"{total_processed} processed, {total_updated} updated, {total_failed} failed")
            
        except Exception as e:
            logger.error(f"Fatal error in ingestion job {job_id}: {e}")
            
            # Update job status to failed
            try:
                job = self.db.query(IngestionJobModel).filter(
                    IngestionJobModel.job_id == job_id
                ).first()
                if job:
                    job.status = JobStatus.FAILED
                    if not job.errors:
                        job.errors = []
                    job.errors.append(f"Fatal error: {e}")
                    self.db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status: {db_error}")
    
    def _should_update_document(self, doctype: str, docname: str, document: Dict[str, Any] = None, force_update: bool = False) -> Tuple[bool, str]:
        """Check if document should be updated with duplicate detection logic
        
        Args:
            doctype: Document type
            docname: Document name
            document: Document data (optional, for timestamp comparison)
            force_update: Whether to force update regardless of existing data
            
        Returns:
            Tuple of (should_update, reason)
        """
        if force_update:
            return True, "forced_update"
        
        try:
            # Check if we have existing chunks for this document
            existing_chunks = self._get_existing_chunks(doctype, docname)
            
            if not existing_chunks:
                return True, "new_document"
            
            # Compare modification timestamps if available
            if document and 'modified' in document:
                from datetime import datetime
                import dateutil.parser
                
                try:
                    doc_modified = dateutil.parser.parse(document['modified'])
                    last_processed = existing_chunks.get('last_processed')
                    
                    if last_processed:
                        if isinstance(last_processed, str):
                            last_processed = dateutil.parser.parse(last_processed)
                        
                        if doc_modified > last_processed:
                            return True, "document_updated"
                    else:
                        return True, "missing_timestamp"
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing timestamps for {doctype}/{docname}: {e}")
                    return True, "timestamp_parse_error"
            
            # Check if configuration has changed since last processing
            config_changed = self._has_config_changed(doctype, existing_chunks.get('config_hash'))
            if config_changed:
                return True, "config_changed"
            
            # Check if document content has changed (basic hash comparison)
            if document:
                current_hash = self._calculate_document_hash(document)
                stored_hash = existing_chunks.get('content_hash')
                
                if stored_hash and current_hash != stored_hash:
                    return True, "content_changed"
                elif not stored_hash:
                    return True, "missing_content_hash"
            
            return False, "up_to_date"
            
        except Exception as e:
            logger.warning(f"Error checking document update status for {doctype}/{docname}: {e}")
            # Default to updating if we can't determine status
            return True, "error_checking_status"
    
    def _get_existing_chunks(self, doctype: str, docname: str) -> Dict[str, Any]:
        """Get existing chunks for a document (placeholder for vector DB query)
        
        Args:
            doctype: Document type
            docname: Document name
            
        Returns:
            Dictionary with existing chunk information
        """
        # This is a placeholder - in a real implementation, you would:
        # 1. Query the vector database for existing chunks
        # 2. Return metadata about when they were last processed
        
        # For now, simulate some existing data for demonstration with more realistic logic
        import random
        import hashlib
        
        # Create a deterministic "hash" based on doctype/docname for consistent testing
        doc_key = f"{doctype}:{docname}"
        doc_hash = int(hashlib.md5(doc_key.encode()).hexdigest()[:8], 16)
        
        # Use hash to determine if document "exists" (30% chance)
        if doc_hash % 10 < 3:
            return {
                'chunk_count': (doc_hash % 5) + 1,
                'last_processed': '2024-01-01T00:00:00Z',
                'config_hash': f'config_hash_{doc_hash % 100}',
                'content_hash': f'content_hash_{doc_hash % 1000}'
            }
        return {}
    
    def _has_config_changed(self, doctype: str, stored_config_hash: str = None) -> bool:
        """Check if doctype configuration has changed
        
        Args:
            doctype: Document type
            stored_config_hash: Previously stored configuration hash
            
        Returns:
            True if configuration has changed
        """
        if not stored_config_hash:
            return True
        
        # Get current configuration
        config = self.db.query(DoctypeConfigModel).filter(
            DoctypeConfigModel.doctype == doctype
        ).first()
        
        if not config:
            return True
        
        # Calculate current config hash
        import hashlib
        import json
        
        config_data = {
            'fields': sorted(config.fields) if config.fields else [],
            'filters': config.filters or {},
            'chunk_size': config.chunk_size,
            'chunk_overlap': config.chunk_overlap
        }
        
        current_hash = hashlib.md5(
            json.dumps(config_data, sort_keys=True).encode()
        ).hexdigest()
        
        return current_hash != stored_config_hash
    
    def _calculate_document_hash(self, document: Dict[str, Any]) -> str:
        """Calculate hash of document content for change detection
        
        Args:
            document: Document data
            
        Returns:
            MD5 hash of document content
        """
        import hashlib
        import json
        
        # Create a normalized version of the document for hashing
        # Exclude metadata fields that change frequently
        content_fields = {k: v for k, v in document.items() 
                         if k not in ['modified', 'creation', 'modified_by', 'owner']}
        
        # Sort keys for consistent hashing
        content_str = json.dumps(content_fields, sort_keys=True, default=str)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    async def _process_document_for_embedding(self, doctype: str, document: Dict[str, Any], config: DoctypeConfigModel):
        """Process document for chunking and embedding (placeholder implementation)
        
        Args:
            doctype: Document type
            document: Document data
            config: Doctype configuration
        """
        # This is a placeholder for the actual document processing pipeline
        # In a real implementation, this would:
        # 1. Send document to chunking service
        # 2. Send chunks to embedding service
        # 3. Store embeddings in vector database
        # 4. Update document processing metadata
        
        # Simulate processing time
        import asyncio
        await asyncio.sleep(0.01)  # Small delay to simulate processing
        
        logger.debug(f"Processed document {document['name']} for embedding with {len(document)} fields")
    
    async def process_webhook_ingestion(self, doctype: str, docname: str, action: str):
        """Process webhook-triggered ingestion
        
        Args:
            doctype: Document type
            docname: Document name
            action: Action type (create, update, delete)
        """
        try:
            logger.info(f"Processing webhook ingestion: {action} {doctype}/{docname}")
            
            # Get doctype configuration
            config = self.db.query(DoctypeConfigModel).filter(
                DoctypeConfigModel.doctype == doctype
            ).first()
            
            if not config or not config.enabled:
                logger.info(f"Doctype {doctype} not configured or disabled, ignoring webhook")
                return
            
            if action == "delete":
                # Handle document deletion
                await self._handle_document_deletion(doctype, docname)
            else:
                # Handle document creation/update
                await self._handle_document_upsert(doctype, docname, config)
            
        except Exception as e:
            logger.error(f"Error processing webhook for {doctype}/{docname}: {e}")
    
    async def _handle_document_deletion(self, doctype: str, docname: str):
        """Handle document deletion
        
        Args:
            doctype: Document type
            docname: Document name
        """
        # This would normally delete chunks from vector database
        logger.info(f"Would delete chunks for {doctype}/{docname}")
    
    async def _handle_document_upsert(self, doctype: str, docname: str, config: DoctypeConfigModel):
        """Handle document creation/update
        
        Args:
            doctype: Document type
            docname: Document name
            config: Doctype configuration
        """
        try:
            # Fetch the document
            result = self.document_fetcher.fetch_single_document(
                doctype=doctype,
                docname=docname,
                fields=config.fields
            )
            
            if not result.success:
                logger.error(f"Failed to fetch document {doctype}/{docname}: {result.error}")
                return
            
            if not result.document:
                logger.warning(f"Document {doctype}/{docname} not found or has no content")
                return
            
            # This would normally send to chunking/embedding services
            logger.info(f"Would process document {doctype}/{docname} with {len(result.document)} fields")
            
        except Exception as e:
            logger.error(f"Error handling document upsert for {doctype}/{docname}: {e}")
    
    def get_ingestion_summary(self, job_id: str) -> Dict[str, Any]:
        """Get comprehensive summary of ingestion job
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with detailed job summary
        """
        job = self.db.query(IngestionJobModel).filter(
            IngestionJobModel.job_id == job_id
        ).first()
        
        if not job:
            return {"error": "Job not found"}
        
        # Calculate processing statistics
        total_documents = job.processed + job.failed
        success_rate = (job.processed / total_documents * 100) if total_documents > 0 else 0
        update_rate = (job.updated / job.processed * 100) if job.processed > 0 else 0
        
        # Calculate duration and processing speed
        duration_seconds = None
        processing_speed = None
        
        if job.completed_at and job.created_at:
            duration_seconds = (job.completed_at - job.created_at).total_seconds()
            if duration_seconds > 0:
                processing_speed = total_documents / duration_seconds  # docs per second
        elif job.status == JobStatus.PROCESSING and job.created_at:
            # For ongoing jobs, calculate current duration
            duration_seconds = (datetime.utcnow() - job.created_at).total_seconds()
            if duration_seconds > 0:
                processing_speed = total_documents / duration_seconds
        
        # Get configuration details
        config = self.db.query(DoctypeConfigModel).filter(
            DoctypeConfigModel.doctype == job.doctype
        ).first()
        
        config_info = {}
        if config:
            config_info = {
                "fields": config.fields,
                "filters": config.filters,
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap,
                "last_sync": config.last_sync.isoformat() if config.last_sync else None
            }
        
        # Extract metadata for enhanced reporting
        metadata = job.job_metadata or {}
        total_skipped = metadata.get('total_skipped', 0)
        
        # Build comprehensive summary
        summary = {
            "job_id": job.job_id,
            "doctype": job.doctype,
            "status": job.status,
            "progress": {
                "processed": job.processed,
                "updated": job.updated,
                "skipped": total_skipped,
                "failed": job.failed,
                "total": total_documents,
                "total_available": metadata.get('total_documents', total_documents),
                "success_rate": round(success_rate, 2),
                "update_rate": round(update_rate, 2),
                "skip_rate": round((total_skipped / total_documents * 100), 2) if total_documents > 0 else 0
            },
            "timing": {
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "duration_seconds": duration_seconds,
                "processing_speed_docs_per_sec": round(processing_speed, 2) if processing_speed else None,
                "avg_batch_time_seconds": metadata.get('avg_batch_time', 0)
            },
            "batch_processing": {
                "batch_size": job.batch_size,
                "batches_processed": metadata.get('batches_processed', 0),
                "current_batch_size": metadata.get('current_batch_size', 0),
                "avg_documents_per_batch": round(sum(metadata.get('documents_per_batch', [])) / len(metadata.get('documents_per_batch', [1])), 2) if metadata.get('documents_per_batch') else 0
            },
            "configuration": {
                "batch_size": job.batch_size,
                "filters": job.filters,
                "doctype_config": config_info
            },
            "analysis": {
                "update_reasons": metadata.get('update_reasons', {}),
                "error_types": metadata.get('error_types', {}),
                "duplicate_detection": {
                    "new_documents": metadata.get('update_reasons', {}).get('new_document', 0),
                    "updated_documents": metadata.get('update_reasons', {}).get('document_updated', 0),
                    "forced_updates": metadata.get('update_reasons', {}).get('forced_update', 0),
                    "config_changes": metadata.get('update_reasons', {}).get('config_changed', 0),
                    "up_to_date": total_skipped
                }
            },
            "errors": {
                "count": len(job.errors) if job.errors else 0,
                "recent_errors": job.errors[-10:] if job.errors else [],  # Last 10 errors
                "has_more_errors": len(job.errors) > 10 if job.errors else False,
                "error_breakdown": metadata.get('error_types', {})
            }
        }
        
        return summary
    
    def get_ingestion_statistics(self, doctype: str = None, limit_days: int = 30) -> Dict[str, Any]:
        """Get ingestion statistics for analysis
        
        Args:
            doctype: Optional doctype filter
            limit_days: Number of days to look back
            
        Returns:
            Dictionary with ingestion statistics
        """
        from datetime import timedelta
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=limit_days)
        
        # Build query
        query = self.db.query(IngestionJobModel).filter(
            IngestionJobModel.created_at >= start_date
        )
        
        if doctype:
            query = query.filter(IngestionJobModel.doctype == doctype)
        
        jobs = query.all()
        
        if not jobs:
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": limit_days
                },
                "summary": {
                    "total_jobs": 0,
                    "total_documents": 0,
                    "total_updated": 0,
                    "total_failed": 0
                },
                "by_status": {},
                "by_doctype": {},
                "performance": {}
            }
        
        # Calculate summary statistics
        total_jobs = len(jobs)
        total_documents = sum(job.processed + job.failed for job in jobs)
        total_updated = sum(job.updated for job in jobs)
        total_failed = sum(job.failed for job in jobs)
        
        # Group by status
        by_status = {}
        for job in jobs:
            status = job.status
            if status not in by_status:
                by_status[status] = {"count": 0, "documents": 0}
            by_status[status]["count"] += 1
            by_status[status]["documents"] += job.processed + job.failed
        
        # Group by doctype
        by_doctype = {}
        for job in jobs:
            dt = job.doctype
            if dt not in by_doctype:
                by_doctype[dt] = {
                    "jobs": 0,
                    "documents": 0,
                    "updated": 0,
                    "failed": 0
                }
            by_doctype[dt]["jobs"] += 1
            by_doctype[dt]["documents"] += job.processed + job.failed
            by_doctype[dt]["updated"] += job.updated
            by_doctype[dt]["failed"] += job.failed
        
        # Calculate performance metrics
        completed_jobs = [job for job in jobs if job.status == JobStatus.COMPLETED and job.completed_at]
        
        performance = {}
        if completed_jobs:
            durations = []
            speeds = []
            
            for job in completed_jobs:
                duration = (job.completed_at - job.created_at).total_seconds()
                durations.append(duration)
                
                total_docs = job.processed + job.failed
                if duration > 0 and total_docs > 0:
                    speeds.append(total_docs / duration)
            
            if durations:
                performance["average_duration_seconds"] = sum(durations) / len(durations)
                performance["min_duration_seconds"] = min(durations)
                performance["max_duration_seconds"] = max(durations)
            
            if speeds:
                performance["average_speed_docs_per_sec"] = sum(speeds) / len(speeds)
                performance["min_speed_docs_per_sec"] = min(speeds)
                performance["max_speed_docs_per_sec"] = max(speeds)
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": limit_days,
                "doctype_filter": doctype
            },
            "summary": {
                "total_jobs": total_jobs,
                "total_documents": total_documents,
                "total_updated": total_updated,
                "total_failed": total_failed,
                "success_rate": round((total_documents - total_failed) / total_documents * 100, 2) if total_documents > 0 else 0,
                "update_rate": round(total_updated / total_documents * 100, 2) if total_documents > 0 else 0
            },
            "by_status": by_status,
            "by_doctype": by_doctype,
            "performance": performance
        }