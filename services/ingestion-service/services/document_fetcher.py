"""
Document fetcher service for retrieving documents from Frappe
"""

import logging
from typing import Dict, List, Any, Optional, Generator, Tuple
from dataclasses import dataclass

from frappe_client import FrappeClient, FrappeAPIError

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of document fetching operation"""
    success: bool
    document: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    doctype: Optional[str] = None
    docname: Optional[str] = None


@dataclass
class BatchFetchResult:
    """Result of batch document fetching"""
    total_requested: int
    total_fetched: int
    successful: List[Dict[str, Any]]
    failed: List[FetchResult]
    errors: List[str]


class DocumentFetcher:
    """Service for fetching documents from Frappe with error handling and field selection"""
    
    def __init__(self, frappe_client: FrappeClient = None):
        """Initialize document fetcher
        
        Args:
            frappe_client: Frappe client instance (optional)
        """
        self.client = frappe_client
        if not self.client:
            from frappe_client import get_frappe_client
            self.client = get_frappe_client()
    
    def fetch_single_document(self, 
                            doctype: str, 
                            docname: str, 
                            fields: List[str] = None) -> FetchResult:
        """Fetch a single document with error handling
        
        Args:
            doctype: Document type
            docname: Document name/ID
            fields: List of fields to fetch
            
        Returns:
            FetchResult with document data or error information
        """
        try:
            logger.debug(f"Fetching document: {doctype}/{docname}")
            
            if fields:
                # Use the field-specific method for better error handling
                document = self.client.get_document_fields(doctype, docname, fields)
            else:
                document = self.client.get_document(doctype, docname)
            
            if not document:
                return FetchResult(
                    success=False,
                    error="Document not found",
                    doctype=doctype,
                    docname=docname
                )
            
            # Filter out empty fields if specific fields were requested
            if fields:
                filtered_doc = {}
                for field in fields:
                    value = document.get(field)
                    if value is not None and str(value).strip():
                        filtered_doc[field] = value
                document = filtered_doc
            
            return FetchResult(
                success=True,
                document=document,
                doctype=doctype,
                docname=docname
            )
            
        except FrappeAPIError as e:
            logger.error(f"Frappe API error fetching {doctype}/{docname}: {e}")
            return FetchResult(
                success=False,
                error=f"Frappe API error: {e}",
                doctype=doctype,
                docname=docname
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching {doctype}/{docname}: {e}")
            return FetchResult(
                success=False,
                error=f"Unexpected error: {e}",
                doctype=doctype,
                docname=docname
            )
    
    def fetch_documents_batch(self,
                            doctype: str,
                            fields: List[str] = None,
                            filters: Dict[str, Any] = None,
                            limit: int = 100,
                            offset: int = 0) -> BatchFetchResult:
        """Fetch multiple documents in a batch with error handling
        
        Args:
            doctype: Document type
            fields: List of fields to fetch
            filters: Filters to apply
            limit: Maximum number of documents to fetch
            offset: Number of documents to skip
            
        Returns:
            BatchFetchResult with successful and failed documents
        """
        try:
            logger.info(f"Fetching batch: {doctype}, limit={limit}, offset={offset}")
            
            documents, total_count = self.client.get_documents(
                doctype=doctype,
                fields=fields,
                filters=filters,
                limit=limit,
                offset=offset,
                order_by="modified desc"  # Get most recently modified first
            )
            
            successful = []
            failed = []
            errors = []
            
            for doc in documents:
                try:
                    # Validate document has required fields
                    if not doc.get('name'):
                        failed.append(FetchResult(
                            success=False,
                            error="Document missing 'name' field",
                            doctype=doctype,
                            document=doc
                        ))
                        continue
                    
                    # Filter out empty fields if specific fields were requested
                    if fields:
                        filtered_doc = {'name': doc['name']}  # Always include name
                        has_content = False
                        
                        for field in fields:
                            if field == 'name':
                                continue
                            value = doc.get(field)
                            if value is not None and str(value).strip():
                                filtered_doc[field] = value
                                has_content = True
                        
                        # Only include documents that have at least one content field
                        if has_content:
                            successful.append(filtered_doc)
                        else:
                            logger.debug(f"Skipping {doctype}/{doc['name']} - no content in specified fields")
                    else:
                        successful.append(doc)
                        
                except Exception as e:
                    error_msg = f"Error processing document {doc.get('name', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    failed.append(FetchResult(
                        success=False,
                        error=str(e),
                        doctype=doctype,
                        docname=doc.get('name', 'unknown'),
                        document=doc
                    ))
            
            return BatchFetchResult(
                total_requested=len(documents),
                total_fetched=len(successful),
                successful=successful,
                failed=failed,
                errors=errors
            )
            
        except FrappeAPIError as e:
            logger.error(f"Frappe API error fetching {doctype} batch: {e}")
            return BatchFetchResult(
                total_requested=0,
                total_fetched=0,
                successful=[],
                failed=[],
                errors=[f"Frappe API error: {e}"]
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching {doctype} batch: {e}")
            return BatchFetchResult(
                total_requested=0,
                total_fetched=0,
                successful=[],
                failed=[],
                errors=[f"Unexpected error: {e}"]
            )
    
    def fetch_documents_generator(self,
                                doctype: str,
                                fields: List[str] = None,
                                filters: Dict[str, Any] = None,
                                batch_size: int = 100) -> Generator[BatchFetchResult, None, None]:
        """Generator that yields batches of documents
        
        Args:
            doctype: Document type
            fields: List of fields to fetch
            filters: Filters to apply
            batch_size: Size of each batch
            
        Yields:
            BatchFetchResult for each batch
        """
        offset = 0
        total_processed = 0
        
        while True:
            batch_result = self.fetch_documents_batch(
                doctype=doctype,
                fields=fields,
                filters=filters,
                limit=batch_size,
                offset=offset
            )
            
            # Yield the batch result
            yield batch_result
            
            # Update counters
            total_processed += batch_result.total_fetched
            offset += batch_size
            
            # Stop if we got fewer documents than requested (end of data)
            if batch_result.total_requested < batch_size:
                logger.info(f"Completed fetching {doctype}: {total_processed} documents processed")
                break
            
            # Stop if there were errors and no successful documents
            if batch_result.errors and not batch_result.successful:
                logger.error(f"Stopping batch processing due to errors: {batch_result.errors}")
                break
    
    def get_document_count(self, 
                          doctype: str, 
                          filters: Dict[str, Any] = None) -> int:
        """Get total count of documents matching filters
        
        Args:
            doctype: Document type
            filters: Filters to apply
            
        Returns:
            Total count of matching documents
        """
        try:
            # Fetch a small batch to get the total count
            _, total_count = self.client.get_documents(
                doctype=doctype,
                fields=["name"],
                filters=filters,
                limit=1
            )
            return total_count
            
        except Exception as e:
            logger.error(f"Failed to get document count for {doctype}: {e}")
            return 0
    
    def validate_doctype_fields(self, 
                              doctype: str, 
                              fields: List[str]) -> Tuple[List[str], List[str]]:
        """Validate that fields exist for a doctype by testing with a sample document
        
        Args:
            doctype: Document type
            fields: List of fields to validate
            
        Returns:
            Tuple of (valid_fields, invalid_fields)
        """
        try:
            # Get a sample document to test field availability
            documents, _ = self.client.get_documents(
                doctype=doctype,
                limit=1,
                fields=["name"]
            )
            
            if not documents:
                logger.warning(f"No documents found for doctype {doctype}")
                return [], fields
            
            sample_doc = self.client.get_document(doctype, documents[0]['name'])
            if not sample_doc:
                return [], fields
            
            valid_fields = []
            invalid_fields = []
            
            for field in fields:
                if field in sample_doc:
                    valid_fields.append(field)
                else:
                    invalid_fields.append(field)
            
            if invalid_fields:
                logger.warning(f"Invalid fields for {doctype}: {invalid_fields}")
            
            return valid_fields, invalid_fields
            
        except Exception as e:
            logger.error(f"Failed to validate fields for {doctype}: {e}")
            return [], fields