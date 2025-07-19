"""
Frappe API client for document fetching
"""

import requests
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings

logger = logging.getLogger(__name__)


class FrappeAPIError(Exception):
    """Custom exception for Frappe API errors"""
    pass


class FrappeClient:
    """Client for interacting with Frappe API"""
    
    def __init__(self, base_url: str = None, api_key: str = None, api_secret: str = None):
        """Initialize Frappe client
        
        Args:
            base_url: Frappe instance URL
            api_key: API key for authentication
            api_secret: API secret for authentication
        """
        self.base_url = base_url or settings.frappe_url
        self.api_key = api_key or settings.frappe_api_key
        self.api_secret = api_secret or settings.frappe_api_secret
        
        if not all([self.base_url, self.api_key, self.api_secret]):
            raise ValueError("Frappe URL, API key, and API secret are required")
        
        # Ensure base URL ends with /
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=settings.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'Authorization': f'token {self.api_key}:{self.api_secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        logger.info(f"Initialized Frappe client for {self.base_url}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Frappe API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests
            
        Returns:
            Response data as dictionary
            
        Raises:
            FrappeAPIError: If request fails
        """
        url = urljoin(self.base_url, endpoint)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=settings.request_timeout,
                **kwargs
            )
            
            # Log request details
            logger.debug(f"{method} {url} - Status: {response.status_code}")
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Check for Frappe-specific errors
            if not data.get('message', {}).get('success', True):
                error_msg = data.get('message', {}).get('error', 'Unknown Frappe error')
                raise FrappeAPIError(f"Frappe API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise FrappeAPIError(f"Request failed: {e}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise FrappeAPIError(f"Invalid JSON response: {e}")
    
    def get_document(self, doctype: str, docname: str, fields: List[str] = None) -> Dict[str, Any]:
        """Fetch a single document from Frappe
        
        Args:
            doctype: Document type
            docname: Document name/ID
            fields: List of fields to fetch (optional)
            
        Returns:
            Document data
            
        Raises:
            FrappeAPIError: If document fetch fails
        """
        endpoint = f"api/resource/{doctype}/{docname}"
        
        params = {}
        if fields:
            params['fields'] = json.dumps(fields)
        
        try:
            response = self._make_request('GET', endpoint, params=params)
            return response.get('data', {})
            
        except FrappeAPIError as e:
            if "404" in str(e):
                logger.warning(f"Document not found: {doctype}/{docname}")
                return None
            raise
    
    def get_documents(self, 
                     doctype: str, 
                     fields: List[str] = None, 
                     filters: Dict[str, Any] = None,
                     limit: int = None,
                     offset: int = 0,
                     order_by: str = None) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch multiple documents from Frappe
        
        Args:
            doctype: Document type
            fields: List of fields to fetch
            filters: Filters to apply
            limit: Maximum number of documents to fetch
            offset: Number of documents to skip
            order_by: Field to order by
            
        Returns:
            Tuple of (documents list, total count)
            
        Raises:
            FrappeAPIError: If document fetch fails
        """
        endpoint = f"api/resource/{doctype}"
        
        params = {
            'limit_start': offset,
        }
        
        if fields:
            params['fields'] = json.dumps(fields)
        
        if filters:
            params['filters'] = json.dumps(filters)
        
        if limit:
            params['limit_page_length'] = limit
        
        if order_by:
            params['order_by'] = order_by
        
        try:
            response = self._make_request('GET', endpoint, params=params)
            data = response.get('data', [])
            
            # Get total count from headers or make separate count request
            total_count = len(data)
            if limit and len(data) == limit:
                # Might be more records, get actual count
                count_response = self._make_request('GET', endpoint, params={
                    'filters': json.dumps(filters) if filters else None,
                    'limit_page_length': 1,
                    'fields': '["name"]'
                })
                # This is a simplified approach - in practice, you might need
                # to use Frappe's count API or iterate through pages
                total_count = len(count_response.get('data', []))
            
            return data, total_count
            
        except FrappeAPIError:
            logger.error(f"Failed to fetch documents for doctype: {doctype}")
            raise
    
    def get_document_fields(self, doctype: str, docname: str, field_names: List[str]) -> Dict[str, Any]:
        """Get specific fields from a document with error handling
        
        Args:
            doctype: Document type
            docname: Document name/ID
            field_names: List of field names to extract
            
        Returns:
            Dictionary with field values, empty fields are handled gracefully
        """
        try:
            doc = self.get_document(doctype, docname, field_names)
            if not doc:
                logger.warning(f"Document not found: {doctype}/{docname}")
                return {}
            
            # Extract only the requested fields and handle missing ones
            result = {}
            for field in field_names:
                value = doc.get(field)
                if value is not None and str(value).strip():
                    result[field] = value
                else:
                    logger.debug(f"Field '{field}' is empty or missing in {doctype}/{docname}")
            
            return result
            
        except FrappeAPIError as e:
            logger.error(f"Failed to fetch fields for {doctype}/{docname}: {e}")
            return {}
    
    def test_connection(self) -> bool:
        """Test connection to Frappe instance
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to fetch user info as a simple test
            response = self._make_request('GET', 'api/method/frappe.auth.get_logged_user')
            logger.info("Frappe connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Frappe connection test failed: {e}")
            return False


# Global client instance
_frappe_client = None


def get_frappe_client() -> FrappeClient:
    """Get global Frappe client instance"""
    global _frappe_client
    if _frappe_client is None:
        _frappe_client = FrappeClient()
    return _frappe_client