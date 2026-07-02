# -*- coding: utf-8 -*-
import xmlrpc.client
import logging

_logger = logging.getLogger(__name__)


class OdooAPIClient:
    """
    XML-RPC client for connecting to external Odoo instances.
    """

    def __init__(self, url, db, username, password):
        """
        Initialize Odoo API client.

        Args:
            url: Odoo instance URL (e.g., https://instance.odoo.com)
            db: Database name
            username: Username for login
            password: API key or password
        """
        self.url = url.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = None
        self.models = None
        self._authenticated = False

    def authenticate(self):
        """Authenticate with the Odoo instance."""
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = self.common.authenticate(
                self.db, self.username, self.password, {}
            )

            if not self.uid:
                raise Exception('Authentication failed: Invalid credentials')

            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            self._authenticated = True
            _logger.info(f'Successfully authenticated with Odoo: {self.url}')
            return True
        except Exception as e:
            _logger.error(f'Authentication failed: {str(e)}')
            raise

    def is_authenticated(self):
        """Check if authenticated."""
        return self._authenticated

    def search_read(self, model, domain=None, fields=None, limit=None, offset=0):
        """
        Search and read records from external Odoo.

        Args:
            model: Model name (e.g., 'res.partner')
            domain: Search domain
            fields: List of fields to fetch
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of records
        """
        if not self.is_authenticated():
            self.authenticate()

        if domain is None:
            domain = []
        if fields is None:
            fields = []

        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, 'search_read',
                [domain],
                {
                    'fields': fields,
                    'limit': limit,
                    'offset': offset,
                }
            )
        except Exception as e:
            _logger.error(f'Error searching {model}: {str(e)}')
            raise

    def search(self, model, domain=None, limit=None, offset=0):
        """
        Search for record IDs.

        Args:
            model: Model name
            domain: Search domain
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of record IDs
        """
        if not self.is_authenticated():
            self.authenticate()

        if domain is None:
            domain = []

        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, 'search',
                [domain],
                {
                    'limit': limit,
                    'offset': offset,
                }
            )
        except Exception as e:
            _logger.error(f'Error searching {model}: {str(e)}')
            raise

    def read(self, model, ids, fields=None):
        """
        Read records by IDs.

        Args:
            model: Model name
            ids: List of record IDs
            fields: List of fields to fetch

        Returns:
            List of records
        """
        if not self.is_authenticated():
            self.authenticate()

        if fields is None:
            fields = []

        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, 'read',
                [ids],
                {'fields': fields}
            )
        except Exception as e:
            _logger.error(f'Error reading {model}: {str(e)}')
            raise

    def get_model_fields(self, model):
        """
        Get all fields of a model.

        Args:
            model: Model name

        Returns:
            Dictionary of field definitions
        """
        if not self.is_authenticated():
            self.authenticate()

        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, 'fields_get',
                [],
                {'attributes': ['string', 'type', 'required', 'readonly']}
            )
        except Exception as e:
            _logger.error(f'Error getting fields for {model}: {str(e)}')
            raise

    def get_record_count(self, model, domain=None):
        """
        Get total record count.

        Args:
            model: Model name
            domain: Search domain

        Returns:
            Integer count
        """
        if not self.is_authenticated():
            self.authenticate()

        if domain is None:
            domain = []

        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, 'search_count',
                [domain]
            )
        except Exception as e:
            _logger.error(f'Error getting count for {model}: {str(e)}')
            raise