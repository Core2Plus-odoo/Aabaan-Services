# Aabaan Scheduler Import Mapping

## Extracted Workbook Sheets

| Sheet | Rows | Use |
| --- | ---: | --- |
| `1. Customers` | 538 | Import customers into Contacts |
| `8. AMC Contracts Pest Control` | 471 | Import Pest Control contracts |
| `AMC WATER TANK CLEANING` | 161 | Import Water Tank contracts |
| `3. Products` | 33 | Import service products |
| `5. Employees` | 39 | Import technicians and office staff |

## Customer Mapping

| Workbook column | Odoo field |
| --- | --- |
| Customer Code | `ref` |
| Customer Name | `name` |
| Customer Type | `company_type` |
| Phone | `phone` / `mobile` |
| Email | `email` |
| Emirate | custom tag or state/address field |
| Area / Building | `street2` or custom area field |
| Street Address | `street` |
| TRN | `vat` |
| Payment Terms | `property_payment_term_id` |
| Credit Limit | credit-control field if enabled |

## Contract Mapping

| Workbook column | Scheduler field |
| --- | --- |
| Contract Reference | `name` |
| Customer Name | `partner_id` |
| Service Type | `service_type` |
| Frequency | `frequency` or `custom_visit_count` |
| Contract Value (AED) | `contract_value` |
| Billing Cycle Amount | `billing_cycle_amount` |
| Start Date | `start_date` |
| End Date | `end_date` |
| Auto-Renew? | `auto_renew` |
| Notes | `notes` |
| Group | `group_name` |

## Frequency Cleanup Rules

| Source example | Scheduler value |
| --- | --- |
| `2 Times`, `2 TIME` | `2` |
| `12 TIME` | `12` |
| `24 TIME` | `24` |
| `36 TIME` | `36` |
| Any unusual text | `custom` plus `custom_visit_count` |

## Recommended Import Order

1. Products/services
2. Customers
3. Employees
4. Service contracts
5. Generate visits from contracts inside Odoo

Do not import generated visits from Excel unless historical dates must be preserved exactly. For active AMC work, import contracts and let the scheduler create a clean operational calendar.
