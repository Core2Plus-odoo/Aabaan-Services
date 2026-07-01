# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from ..models.odoo_api_client import OdooAPIClient

_logger = logging.getLogger(__name__)


class OdooMasterDataImportWizard(models.TransientModel):
    _name = 'odoo.master.data.import.wizard'
    _description = 'Odoo Master Data Direct Import Wizard'

    source_url = fields.Char(
        string='Source Odoo URL',
        required=True,
        help='URL of the Odoo instance to import from (e.g., https://instance.odoo.com)'
    )
    source_database = fields.Char(
        string='Source Database Name',
        required=True,
        help='Database name of the source Odoo instance'
    )
    source_username = fields.Char(
        string='Username',
        required=True,
        help='Username to authenticate with source Odoo'
    )
    source_api_key = fields.Char(
        string='API Key / Password',
        required=True,
        help='API key or password for authentication'
    )
    import_partners = fields.Boolean(
        string='Import Customers & Vendors',
        default=True,
        help='Import all res.partner records (customers, vendors, employees)'
    )
    import_products = fields.Boolean(
        string='Import Products',
        default=True,
        help='Import all product.product and product.category records'
    )
    import_employees = fields.Boolean(
        string='Import Employees',
        default=True,
        help='Import all hr.employee records'
    )
    import_accounts = fields.Boolean(
        string='Import Chart of Accounts',
        default=False,
        help='Import all account.account and account.journal records'
    )
    import_company = fields.Boolean(
        string='Import Companies',
        default=False,
        help='Import res.company records'
    )
    import_log = fields.Text(
        string='Import Log',
        readonly=True,
        help='Log of the import operation'
    )
    state = fields.Selection(
        [('setup', 'Setup'), ('importing', 'Importing'), ('done', 'Done')],
        string='State',
        default='setup'
    )

    def test_connection(self):
        """Test connection to the source Odoo instance."""
        self.ensure_one()
        try:
            client = OdooAPIClient(
                self.source_url,
                self.source_database,
                self.source_username,
                self.source_api_key
            )
            client.authenticate()
            message = f'✓ Successfully connected to {self.source_url}'
            _logger.info(message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Success',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = f'Connection failed: {str(e)}'
            _logger.error(error_msg)
            raise UserError(error_msg)

    def action_start_import(self):
        """Start the import process."""
        self.ensure_one()

        try:
            log_lines = []
            client = OdooAPIClient(
                self.source_url,
                self.source_database,
                self.source_username,
                self.source_api_key
            )
            client.authenticate()
            log_lines.append('✓ Successfully authenticated with source Odoo')

            # Import companies first (if enabled)
            if self.import_company:
                log_lines.append('\n--- Importing Companies ---')
                self._import_companies(client, log_lines)

            # Import partners (customers, vendors, employees)
            if self.import_partners:
                log_lines.append('\n--- Importing Partners (Customers, Vendors) ---')
                self._import_partners(client, log_lines)

            # Import products
            if self.import_products:
                log_lines.append('\n--- Importing Products ---')
                self._import_products(client, log_lines)

            # Import employees
            if self.import_employees:
                log_lines.append('\n--- Importing Employees ---')
                self._import_employees(client, log_lines)

            # Import accounts (if enabled)
            if self.import_accounts:
                log_lines.append('\n--- Importing Chart of Accounts ---')
                self._import_accounts(client, log_lines)

            log_lines.append('\n✓ Master data import completed successfully')

            # Update wizard state
            self.write({
                'import_log': '\n'.join(log_lines),
                'state': 'done'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete',
                    'message': 'Master data imported successfully',
                    'type': 'success',
                    'sticky': True,
                }
            }

        except Exception as e:
            error_msg = f'Import failed: {str(e)}'
            _logger.error(error_msg, exc_info=True)
            self.write({
                'import_log': error_msg,
                'state': 'done'
            })
            raise UserError(error_msg)

    def _import_companies(self, client, log_lines):
        """Import res.company records."""
        try:
            companies = client.search_read(
                'res.company',
                fields=['id', 'name', 'country_id', 'website', 'email', 'phone']
            )
            log_lines.append(f'Found {len(companies)} companies')

            for company in companies:
                existing = self.env['res.company'].search([
                    ('name', '=', company['name'])
                ], limit=1)

                if not existing:
                    self.env['res.company'].create({
                        'name': company['name'],
                        'website': company.get('website', ''),
                        'email': company.get('email', ''),
                        'phone': company.get('phone', ''),
                    })
                    log_lines.append(f'✓ Created company: {company["name"]}')
                else:
                    log_lines.append(f'⊘ Company already exists: {company["name"]}')

        except Exception as e:
            log_lines.append(f'✗ Error importing companies: {str(e)}')
            raise

    def _import_partners(self, client, log_lines):
        """Import res.partner records."""
        try:
            partners = client.search_read(
                'res.partner',
                fields=[
                    'id', 'name', 'email', 'phone', 'mobile', 'website',
                    'street', 'city', 'state_id', 'zip', 'country_id',
                    'is_company', 'customer_rank', 'supplier_rank'
                ]
            )
            log_lines.append(f'Found {len(partners)} partners')

            created_count = 0
            skipped_count = 0

            for partner in partners:
                existing = self.env['res.partner'].search([
                    '|',
                    ('name', '=', partner['name']),
                    ('email', '=', partner.get('email', ''))
                ], limit=1)

                if not existing:
                    try:
                        self.env['res.partner'].create({
                            'name': partner['name'],
                            'email': partner.get('email', ''),
                            'phone': partner.get('phone', ''),
                            'mobile': partner.get('mobile', ''),
                            'website': partner.get('website', ''),
                            'street': partner.get('street', ''),
                            'city': partner.get('city', ''),
                            'zip': partner.get('zip', ''),
                            'is_company': partner.get('is_company', False),
                            'customer': partner.get('customer_rank', 0) > 0,
                            'supplier': partner.get('supplier_rank', 0) > 0,
                        })
                        created_count += 1
                    except Exception as e:
                        log_lines.append(f'✗ Error creating partner {partner["name"]}: {str(e)}')
                else:
                    skipped_count += 1

            log_lines.append(f'✓ Created {created_count} new partners')
            if skipped_count > 0:
                log_lines.append(f'⊘ Skipped {skipped_count} existing partners')

        except Exception as e:
            log_lines.append(f'✗ Error importing partners: {str(e)}')
            raise

    def _import_products(self, client, log_lines):
        """Import product.product and product.category records."""
        try:
            # Import categories first
            categories = client.search_read(
                'product.category',
                fields=['id', 'name', 'parent_id']
            )
            log_lines.append(f'Found {len(categories)} product categories')

            category_map = {}
            for category in categories:
                existing = self.env['product.category'].search([
                    ('name', '=', category['name'])
                ], limit=1)

                if not existing:
                    new_cat = self.env['product.category'].create({
                        'name': category['name'],
                    })
                    category_map[category['id']] = new_cat.id
                    log_lines.append(f'✓ Created product category: {category["name"]}')
                else:
                    category_map[category['id']] = existing.id
                    log_lines.append(f'⊘ Category already exists: {category["name"]}')

            # Import products
            products = client.search_read(
                'product.product',
                fields=[
                    'id', 'name', 'default_code', 'barcode', 'categ_id',
                    'type', 'list_price', 'standard_price', 'uom_id',
                    'description', 'active'
                ]
            )
            log_lines.append(f'Found {len(products)} products')

            created_count = 0
            skipped_count = 0

            for product in products:
                existing = self.env['product.product'].search([
                    '|',
                    ('name', '=', product['name']),
                    ('default_code', '=', product.get('default_code', ''))
                ], limit=1)

                if not existing:
                    try:
                        categ_id = category_map.get(
                            product.get('categ_id', [False])[0],
                            self.env.ref('product.product_category_all').id
                        )
                        self.env['product.product'].create({
                            'name': product['name'],
                            'default_code': product.get('default_code', ''),
                            'barcode': product.get('barcode', ''),
                            'categ_id': categ_id,
                            'type': product.get('type', 'product'),
                            'list_price': product.get('list_price', 0),
                            'standard_price': product.get('standard_price', 0),
                            'description': product.get('description', ''),
                        })
                        created_count += 1
                    except Exception as e:
                        log_lines.append(f'✗ Error creating product {product["name"]}: {str(e)}')
                else:
                    skipped_count += 1

            log_lines.append(f'✓ Created {created_count} new products')
            if skipped_count > 0:
                log_lines.append(f'⊘ Skipped {skipped_count} existing products')

        except Exception as e:
            log_lines.append(f'✗ Error importing products: {str(e)}')
            raise

    def _import_employees(self, client, log_lines):
        """Import hr.employee records."""
        try:
            employees = client.search_read(
                'hr.employee',
                fields=[
                    'id', 'name', 'email', 'work_phone', 'mobile_phone',
                    'job_title', 'department_id', 'manager_id', 'active'
                ]
            )
            log_lines.append(f'Found {len(employees)} employees')

            created_count = 0
            skipped_count = 0

            for employee in employees:
                existing = self.env['hr.employee'].search([
                    '|',
                    ('name', '=', employee['name']),
                    ('email', '=', employee.get('email', ''))
                ], limit=1)

                if not existing:
                    try:
                        self.env['hr.employee'].create({
                            'name': employee['name'],
                            'email': employee.get('email', ''),
                            'work_phone': employee.get('work_phone', ''),
                            'mobile_phone': employee.get('mobile_phone', ''),
                            'job_title': employee.get('job_title', ''),
                        })
                        created_count += 1
                    except Exception as e:
                        log_lines.append(f'✗ Error creating employee {employee["name"]}: {str(e)}')
                else:
                    skipped_count += 1

            log_lines.append(f'✓ Created {created_count} new employees')
            if skipped_count > 0:
                log_lines.append(f'⊘ Skipped {skipped_count} existing employees')

        except Exception as e:
            log_lines.append(f'✗ Error importing employees: {str(e)}')
            raise

    def _import_accounts(self, client, log_lines):
        """Import account.account and account.journal records."""
        try:
            accounts = client.search_read(
                'account.account',
                fields=['id', 'name', 'code', 'account_type', 'company_id']
            )
            log_lines.append(f'Found {len(accounts)} accounts')

            created_count = 0
            skipped_count = 0

            for account in accounts:
                existing = self.env['account.account'].search([
                    ('code', '=', account['code']),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)

                if not existing:
                    try:
                        self.env['account.account'].create({
                            'name': account['name'],
                            'code': account['code'],
                        })
                        created_count += 1
                    except Exception as e:
                        log_lines.append(f'✗ Error creating account {account["code"]}: {str(e)}')
                else:
                    skipped_count += 1

            log_lines.append(f'✓ Created {created_count} new accounts')
            if skipped_count > 0:
                log_lines.append(f'⊘ Skipped {skipped_count} existing accounts')

        except Exception as e:
            log_lines.append(f'✗ Error importing accounts: {str(e)}')
            raise
