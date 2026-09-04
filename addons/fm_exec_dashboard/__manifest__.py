# -*- coding: utf-8 -*-
{
    "name": "Aabaan Executive Dashboard",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "CEO dashboard — revenue, expenses and cash, by period and branch",
    "description": """
Aabaan Executive Dashboard
==========================
The CEO pack the business already works from, rendered live from the
database instead of assembled by hand:

1. **Overview** — revenue against target, jobs completed, new clients,
   receivables and overdue, a city-and-team table, revenue trend stacked by
   branch, service-line mix, salesperson performance, receivables aging, job
   status and the largest open balances.
2. **Expenses** — total spend, net profit and margin, payroll share, monthly
   expense trend with the revenue line over it, spend by category and by
   city, and an expense detail table.
3. **Cash & Bank** — balances per bank and cash journal, inflow and outflow,
   net movement, the flow trend and recent transactions.

Every figure is read from posted records. Nothing is estimated, and where a
number cannot be derived — a branch with no target, a period with no prior
period — the dashboard shows a dash rather than a zero, because zero is a
claim and a dash is not.

Periods are chosen from presets (this/last week, month, quarter, year) or a
custom range, and every "vs prior period" compares against a window of the
same length immediately before it.

Separate from ``fm_ceo_dashboard``, which reports the contract portfolio,
operations load and compliance risk. Both can be installed together; they
answer different questions.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_branding",
        "fm_branch",
        "fm_fsm",
        "account",
    ],
    "data": [
        "views/fm_branch_views.xml",
        "views/account_move_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_exec_dashboard/static/src/exec_dashboard/exec_dashboard.scss",
            "fm_exec_dashboard/static/src/exec_dashboard/exec_dashboard.js",
            "fm_exec_dashboard/static/src/exec_dashboard/exec_dashboard.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
