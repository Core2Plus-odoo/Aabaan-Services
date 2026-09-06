# -*- coding: utf-8 -*-
{
    'name': 'FM Command Centre',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Seven-tab live executive dashboard: overview, field ops, sales, finance, expenses, cash, AMC renewals',
    'description': """
The Executive Command Centre, on the FM platform — seven tabs, each loaded
on demand, every figure drillable to the records behind it, and a period
selector that compares each window against the previous window of the same
length.

Ported from the aabaan build rather than rewritten, and deliberately still
runs on both. The same business fact is spelled differently on the two
platforms (a contract's service line is ``fm_service_line`` here and a
manual ``x_service_line`` there), so the dashboard asks for a *concept* and
takes whichever spelling the database actually has. A concept nothing
answers collapses its own section into an honest empty state.

- Executive Overview — contracted book, quotations, pipeline, receivables,
  customers; period block with like-for-like deltas; 12-month invoiced
  revenue and cash-collected trends; top customers by share of book.
- Field Operations — visits completed, first-time-fix rate (completed
  without a follow-up being raised), SLA-clean rate, average time on site
  from real check-in/check-out stamps; live attention cards; technicians by
  visits and hours; open visits by stage, type and emirate.
- Sales & CRM — contracts signed with delta, open quotations, quotation
  conversion, open pipeline by stage, win rate over decided leads, lead
  sources, lost reasons, contract size mix.
- Finance — receivables, invoiced, collected, collection ratio, days sales
  outstanding (inputs shown on screen), five-band ageing from the due date,
  recovery classification, invoiced-against-collected, top debtors.
- Expenses & Margin — total spend, invoiced, what is left after it and the
  margin, payroll share; invoiced against spent over 12 months; where the
  money went, by expense account; cost by emirate off the Emirate analytic
  dimension. Spend is read from the accounts it was booked to, so payroll
  journals count alongside vendor bills.
- Cash & Bank — balance across the bank and cash accounts, money in, money
  out, net movement, the 12-month flow, balance per account and recent
  movements. Not split by emirate: a bank account belongs to the company,
  not a branch.
- AMC & Renewals — renewal buckets and 12-month timeline, contracts at risk
  with the evidence stated per contract, compliance documents expiring.

Design rules held throughout: aggregation batched via _read_group;
platform fields resolved at runtime so a missing one collapses its own
section instead of raising; and no figure estimated — where a number cannot
be derived from real records it is left out and the reason is stated on
screen. Menu: FM → Command Centre (FM account managers and up).
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'fm_fsm',
        'fm_compliance',
        'account',
        'crm',
    ],
    'data': [
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fm_command_centre/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
