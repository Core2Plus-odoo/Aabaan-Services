# -*- coding: utf-8 -*-
{
    # RETIRED STUB. The XML-RPC master-data importer (customers/products/
    # employees from the old instance) has done its job. Empty stub +
    # pre-migration purges residual records - INCLUDING saved connection configs
    # that held source API keys - on the production upgrade; uninstall from Apps,
    # then delete from source.
    "name": "FM Data Import (retired)",
    "version": "19.0.9.0.0",
    "category": "Facility Management",
    "summary": "Retired one-off data importer - empty stub, self-cleaning.",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
