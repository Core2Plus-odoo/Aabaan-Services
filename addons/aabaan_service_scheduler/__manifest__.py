{
    "name": "Aabaan Service Scheduler",
    "summary": "Easy scheduling for pest control and water tank service visits",
    "version": "19.0.1.1.0",
    "category": "Services",
    "author": "Core2Plus",
    "license": "LGPL-3",
    "depends": [
        "base",
        "hr",
        "sale_management",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/aabaan_service_contract_views.xml",
        "views/aabaan_service_visit_views.xml",
        "views/wizard_views.xml",
        "views/menu_views.xml",
    ],
    "application": True,
    "installable": True,
}
