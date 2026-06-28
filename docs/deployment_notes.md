# Aabaan Odoo Deployment Notes

## Source

- URL: `https://aaban-classic-building-cleaning-llc.odoo.com`
- User: `aabancleaningandpestcontrol@gmail.com`

## Target

- URL: `https://core2plus-odoo-aabaan-services.odoo.com`
- Database: `core2plus-odoo-aabaan-services-main-34150667`
- User: `muhammad.umer@core2plus.com`

## What Can Be Deployed By API

The migration helper can export from the old instance and import into the new instance:

- Customers
- Vendors
- Products/services
- Employees

The script does a dry run by default. Add `-ImportToTarget` only when ready to write records to the new database.

## Scheduler Deployment Constraint

The Python addon `aabaan_service_scheduler` is ready for Odoo.sh or self-hosted Odoo.

For standard Odoo Online, custom Python addons usually cannot be installed. The scheduler should then be implemented with one of these paths:

1. Move the database to Odoo.sh and install the addon.
2. Rebuild the scheduler in Odoo Studio using custom models for service contracts and visits.
3. Use built-in Field Service, Planning, Calendar, Sales, and Subscriptions with light Studio customization.

## Secret Handling

API keys are intentionally not saved in scripts or documentation. Pass them at runtime through prompts or environment variables:

```powershell
$env:AABAAN_SOURCE_ODOO_API_KEY = "..."
$env:AABAAN_TARGET_ODOO_API_KEY = "..."
```

After migration, regenerate both API keys because they were shared during implementation.
