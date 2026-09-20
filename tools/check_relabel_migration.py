# -*- coding: utf-8 -*-
"""Verify the relabel migration against a real Postgres with real jsonb.

Run it against a throwaway cluster, not a live database:

    initdb -D /tmp/pg -A trust
    pg_ctl -D /tmp/pg -o "-p 55444 -k /tmp" start
    python3 tools/check_relabel_migration.py


The fixture declares field_description as jsonb because production does.
A varchar fixture proves only that the SQL parses -- that is exactly how
the first version of this migration reached production and took the
build down.
"""
import importlib.util, sys
import psycopg2

spec = importlib.util.spec_from_file_location(
    "relabel",
    "/home/user/Aabaan-Services/addons/fm_contract/migrations/19.0.3.9.0/post-migration.py")
relabel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relabel)

conn = psycopg2.connect(host="/tmp", port=55444, user="postgres", dbname="postgres")
conn.autocommit = True
cr = conn.cursor()

cr.execute("DROP TABLE IF EXISTS ir_model_fields")
cr.execute("""
    CREATE TABLE ir_model_fields (
        id serial PRIMARY KEY,
        name varchar NOT NULL,
        model varchar NOT NULL,
        state varchar NOT NULL,
        field_description jsonb          -- production's type, not varchar
    )
""")

def add(name, model, state, desc):
    cr.execute("INSERT INTO ir_model_fields (name, model, state, field_description)"
               " VALUES (%s,%s,%s,%s) RETURNING id", (name, model, state, desc))
    return cr.fetchone()[0]

import json
J = json.dumps

# The three real collisions this upgrade logged.
x_prem  = add("x_premises_type",   "sale.order", "manual", J({"en_US": "Premises Type"}))
add("fm_premises_type",  "sale.order", "base",   J({"en_US": "Premises Type"}))
x_warr  = add("x_warranty_years",  "sale.order", "manual", J({"en_US": "Warranty (years)"}))
add("fm_warranty_years", "sale.order", "base",   J({"en_US": "Warranty (years)"}))
# A multi-language label: only en_US is rewritten, the others survive.
x_sla   = add("x_complaint_sla",   "sale.order", "manual",
              J({"en_US": "Complaint Response", "ar_001": "الرد"}))
add("fm_complaint_sla",  "sale.order", "base",   J({"en_US": "Complaint Response"}))

# Must NOT be touched:
# a manual field whose label collides with nothing
x_free  = add("x_site_ref",        "sale.order", "manual", J({"en_US": "Site Reference"}))
# a manual field with no en_US key at all -- skipped, not a crash
x_nolang= add("x_licence_no",      "sale.order", "manual", J({"ar_001": "رخصة"}))
add("fm_licence_no",     "sale.order", "base",   J({"en_US": "Licence No"}))
# Odoo's own manual field on another model -- out of scope
x_plan  = add("x_plan4_id", "account.analytic.line", "manual", J({"en_US": "Department"}))
add("department_id", "account.analytic.line", "base", J({"en_US": "Department"}))
# already relabelled by an earlier run -- must not be relabelled twice
x_twice = add("x_visit_frequency", "sale.order", "manual",
              J({"en_US": "Visit Frequency (x_visit_frequency)"}))
add("visit_frequency",   "sale.order", "base",   J({"en_US": "Visit Frequency (x_visit_frequency)"}))

def label(fid, lang="en_US"):
    cr.execute("SELECT field_description ->> %s FROM ir_model_fields WHERE id=%s", (lang, fid))
    return cr.fetchone()[0]

relabel.migrate(cr, "19.0.3.8.0")

fails = []
def check(what, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (what, got, want))
    else:
        print("  ok  %-46s %r" % (what, got))

print("\nRelabelled:")
check("x_premises_type",  label(x_prem),  "Premises Type (x_premises_type)")
check("x_warranty_years", label(x_warr),  "Warranty (years) (x_warranty_years)")
check("x_complaint_sla",  label(x_sla),   "Complaint Response (x_complaint_sla)")

print("\nOther languages survive:")
check("x_complaint_sla ar_001", label(x_sla, "ar_001"), "الرد")

print("\nLeft alone:")
check("x_site_ref (no collision)",  label(x_free),  "Site Reference")
check("x_licence_no (no en_US)",    label(x_nolang), None)
check("x_licence_no ar_001 intact", label(x_nolang, "ar_001"), "رخصة")
check("x_plan4_id (other model)",   label(x_plan),  "Department")
check("x_visit_frequency (already done)", label(x_twice), "Visit Frequency (x_visit_frequency)")

print("\nModule fields untouched:")
cr.execute("SELECT name, field_description ->> 'en_US' FROM ir_model_fields"
           " WHERE state='base' AND name LIKE 'fm_%' ORDER BY name")
for n, d in cr.fetchall():
    print("  %-22s %r" % (n, d))

print("\nIdempotent (second run):")
relabel.migrate(cr, "19.0.3.8.0")
check("x_premises_type after re-run", label(x_prem), "Premises Type (x_premises_type)")

print("\nFresh install (version falsy) is a no-op:")
cr.execute("UPDATE ir_model_fields SET field_description = %s WHERE id=%s",
           (J({"en_US": "Premises Type"}), x_prem))
relabel.migrate(cr, None)
check("x_premises_type on fresh install", label(x_prem), "Premises Type")

print()
if fails:
    for f in fails: print("FAIL", f)
    sys.exit(1)
print("ALL CHECKS PASSED")
