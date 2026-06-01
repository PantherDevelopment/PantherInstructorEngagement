"""
Panther Instructor Engagement Reports - Canvas API Client
Handles all communication with Canvas LMS API
"""

import requests
from typing import List, Dict, Optional, Any
import time
from datetime import datetime
import keyring


class CanvasAPIError(Exception):
    """Custom exception for Canvas API errors"""
    pass


class CanvasAPIClient:
    """Client for Canvas LMS API with focus on instructor engagement data"""
    
    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: int = 30):
        """
        Initialize Canvas API client
        
        Args:
            base_url: Canvas instance URL (e.g., "https://canvas.university.edu")
            api_token: Canvas API token (if None, will attempt to load from keyring)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        # Set API token
        if api_token:
            self.api_token = api_token
        else:
            # Try to load from keyring
            self.api_token = self._load_token_from_keyring()
        
        if self.api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json'
            })
    
    def _load_token_from_keyring(self) -> Optional[str]:
        """Load API token from system keyring"""
        try:
            return keyring.get_password("PantherInstructorEngagement", "canvas_token")
        except Exception:
            return None
    
    def save_token_to_keyring(self, token: str):
        """Save API token to system keyring"""
        try:
            keyring.set_password("PantherInstructorEngagement", "canvas_token", token)
            self.api_token = token
            self.session.headers.update({
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            })
        except Exception as e:
            raise CanvasAPIError(f"Failed to save token: {e}")
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     data: Optional[Dict] = None, _retry: int = 0) -> Any:
        """
        Make a request to Canvas API with error handling, rate limiting,
        and exponential backoff retry (up to 4 attempts).
        """
        MAX_RETRIES = 4
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=self.timeout
            )

            # Rate limit - wait and retry
            if response.status_code == 429:
                if _retry < MAX_RETRIES:
                    wait = int(response.headers.get('Retry-After', 0)) or (2 ** _retry)
                    time.sleep(wait)
                    return self._make_request(method, endpoint, params, data, _retry + 1)
                raise CanvasAPIError("Rate limit exceeded after maximum retries")

            # Server errors (5xx) - retry with backoff
            if response.status_code >= 500 and _retry < MAX_RETRIES:
                time.sleep(2 ** _retry)
                return self._make_request(method, endpoint, params, data, _retry + 1)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise CanvasAPIError("Invalid API token or expired session")
            elif e.response.status_code == 403:
                raise CanvasAPIError("Insufficient permissions to access this resource")
            elif e.response.status_code == 404:
                raise CanvasAPIError(f"Resource not found: {e.response.url}")
            else:
                raise CanvasAPIError(f"HTTP Error: {e}")
        except requests.exceptions.Timeout:
            if _retry < MAX_RETRIES:
                time.sleep(2 ** _retry)
                return self._make_request(method, endpoint, params, data, _retry + 1)
            raise CanvasAPIError("Request timed out after maximum retries")
        except requests.exceptions.ConnectionError:
            if _retry < MAX_RETRIES:
                time.sleep(2 ** _retry)
                return self._make_request(method, endpoint, params, data, _retry + 1)
            raise CanvasAPIError("Connection error - check your internet connection")
        except CanvasAPIError:
            raise
        except Exception as e:
            raise CanvasAPIError(f"Unexpected error: {e}")
    
    def _make_paginated_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Make a paginated GET request, returning all results across all pages."""
        return self._paginate(endpoint, params)

    def _paginate(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Handle pagination for Canvas API requests
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            List of all results across all pages
        """
        if params is None:
            params = {}
        
        params['per_page'] = 100  # Max allowed by Canvas
        
        all_results = []
        url = f"{self.base_url}{endpoint}"
        
        while url:
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                results = response.json()
                
                if isinstance(results, list):
                    all_results.extend(results)
                else:
                    all_results.append(results)
                
                # Check for next page
                links = response.headers.get('Link', '')
                next_url = None
                for link in links.split(','):
                    if 'rel="next"' in link:
                        next_url = link.split(';')[0].strip('<> ')
                        break
                
                url = next_url
                params = None  # URL already includes params
                
            except requests.exceptions.RequestException as e:
                raise CanvasAPIError(f"Pagination error: {e}")
        
        return all_results
    
    def test_connection(self) -> bool:
        """Test API connection and token validity"""
        try:
            self._make_request('GET', '/api/v1/users/self')
            return True
        except CanvasAPIError:
            return False
    
    def get_user_info(self) -> Dict:
        """Get current user information"""
        return self._make_request('GET', '/api/v1/users/self')
    
    def get_accounts(self) -> List[Dict]:
        """
        Get accounts user has admin access to
        
        Returns:
            List of account dictionaries
        """
        try:
            return self._paginate('/api/v1/accounts', {'per_page': 100})
        except CanvasAPIError:
            return []
    
    def get_all_courses_admin(self, include_concluded: bool = False) -> List[Dict]:
        """
        Get ALL courses from all accounts user has admin access to.
        This is the admin mode approach used for instructor engagement reports.
        
        Args:
            include_concluded: Include concluded/completed courses
            
        Returns:
            List of all course dictionaries from all administered accounts
        """
        accounts = self.get_accounts()
        all_courses = []
        
        for account in accounts:
            account_id = account.get('id')
            if account_id:
                try:
                    # Set up parameters for account courses
                    params = {
                        'include[]': ['term', 'total_students', 'teachers'],
                        'per_page': 100,
                        'with_enrollments': 'true'
                    }
                    
                    if include_concluded:
                        params['state[]'] = ['available', 'completed']
                    else:
                        params['state[]'] = ['available']
                    
                    # Get courses from this account
                    courses = self._paginate(
                        f'/api/v1/accounts/{account_id}/courses',
                        params
                    )
                    all_courses.extend(courses)
                    
                except CanvasAPIError as e:
                    # If we can't access this account, continue with others
                    print(f"Warning: Could not access account {account_id}: {e}")
                    continue
        
        return all_courses
    
    def get_courses_for_account(self, account_id: str, include_concluded: bool = False) -> List[Dict]:
        """Get courses from a specific account only"""
        try:
            params = {
                'include[]': ['term', 'total_students', 'teachers'],
                'per_page': 100,
                'with_enrollments': 'true',
                'state[]': ['available', 'completed'] if include_concluded else ['available']
            }
            return self._paginate(f'/api/v1/accounts/{account_id}/courses', params)
        except CanvasAPIError as e:
            print(f"Warning: Could not access account {account_id}: {e}")
            return []

    def get_courses(self, enrollment_type: Optional[str] = None, 
                   include_concluded: bool = False) -> List[Dict]:
        """
        Get courses for the current user (non-admin mode)
        
        Args:
            enrollment_type: Filter by enrollment type (teacher, student, ta, etc.)
            include_concluded: Include concluded courses
            
        Returns:
            List of course dictionaries
        """
        params = {
            'include[]': ['term', 'teachers', 'total_students'],
            'per_page': 100
        }
        
        if enrollment_type:
            params['enrollment_type'] = enrollment_type
        
        if not include_concluded:
            params['enrollment_state'] = 'active'
        
        return self._paginate('/api/v1/courses', params)
    
    def get_account_courses(self, account_id: str = '1', 
                           enrollment_type: Optional[str] = None,
                           term_id: Optional[str] = None) -> List[Dict]:
        """
        Get all courses in an account (admin access required)
        
        Args:
            account_id: Canvas account ID (default '1' for root account)
            enrollment_type: Filter by enrollment type (teacher, etc.)
            term_id: Filter by enrollment term ID
            
        Returns:
            List of course dictionaries
        """
        params = {
            'include[]': ['term', 'teachers', 'total_students'],
            'per_page': 100
        }
        
        if enrollment_type:
            params['enrollment_type'] = enrollment_type
        
        if term_id:
            params['enrollment_term_id'] = term_id
        
        return self._paginate(f'/api/v1/accounts/{account_id}/courses', params)
    
    def get_enrollment_terms(self, account_id: Optional[str] = None) -> List[Dict]:
        """
        Get enrollment terms from all accounts user has admin access to
        
        Args:
            account_id: Specific account ID (optional, if None gets from all admin accounts)
            
        Returns:
            List of enrollment terms
        """
        if account_id:
            # Get terms from specific account
            try:
                # Don't specify workflow_state to get all terms
                params = {
                    'per_page': 100
                }
                print(f"DEBUG: Calling API: /api/v1/accounts/{account_id}/terms with params: {params}")
                result = self._make_request('GET', f'/api/v1/accounts/{account_id}/terms', params)
                print(f"DEBUG: API response keys: {result.keys()}")
                terms = result.get('enrollment_terms', [])
                print(f"DEBUG: Got {len(terms)} terms from response")
                return terms
            except CanvasAPIError as e:
                print(f"DEBUG: CanvasAPIError: {e}")
                return []
        else:
            # Get terms from all admin accounts
            accounts = self.get_accounts()
            all_terms = []
            seen_term_ids = set()
            
            for account in accounts:
                acc_id = account.get('id')
                if acc_id:
                    try:
                        params = {'per_page': 100}
                        result = self._make_request('GET', f'/api/v1/accounts/{acc_id}/terms', params)
                        terms = result.get('enrollment_terms', [])
                        
                        for term in terms:
                            term_id = term.get('id')
                            if term_id and term_id not in seen_term_ids:
                                all_terms.append(term)
                                seen_term_ids.add(term_id)
                    except CanvasAPIError:
                        continue
            
            return all_terms
    
    def get_course(self, course_id: str) -> Dict:
        """Get details for a specific course"""
        params = {'include[]': ['term', 'teachers', 'total_students']}
        return self._make_request('GET', f'/api/v1/courses/{course_id}', params)
    
    def get_course_teachers(self, course_id: str) -> List[Dict]:
        """Get teacher enrollments for a course"""
        params = {
            'type[]': ['TeacherEnrollment', 'TaEnrollment'],
            'per_page': 100
        }
        return self._paginate(f'/api/v1/courses/{course_id}/enrollments', params)
    
    def get_course_students(self, course_id: str) -> List[Dict]:
        """Get student enrollments for a course"""
        params = {
            'type[]': 'StudentEnrollment',
            'state[]': 'active',
            'per_page': 100
        }
        return self._paginate(f'/api/v1/courses/{course_id}/enrollments', params)