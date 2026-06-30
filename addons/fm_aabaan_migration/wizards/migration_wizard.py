# -*- coding: utf-8 -*-
from datetime import datetime, time

from odoo import _, fields, models

CONTRACT_STATE = {
    "draft": "draft",
    "active": "active",
    "expired": "expired",
    "cancelled": "terminated",
}

# aabaan frequency = visits over the contract; approximate an FM cadence.
FREQUENCY = {
    "1": "annual",
    "2": "semi_annual",
    "4": "quarterly",
    "6": "bi_monthly",
    "12": "monthly",
    "24": "fortnightly",
    "36": "weekly",
    "custom": "monthly",
}

VISIT_STAGE = {
    "draft": "draft",
    "scheduled": "assigned",
    "in_progress": "in_progress",
    "done": "completed",
    "missed": "cancelled",
    "cancelled": "cancelled",
}

# Map aabaan service types to an FM service line for the migrated category.
SERVICE_LINE = {
    "pest_control": "pest",
    "water_tank": "plumbing",
    "cleaning": "cleaning",
    "termite": "pest",
    "other": "other",
}


class FmAabaanMigrationWizard(models.TransientModel):
    _name = "fm.aabaan.migration.wizard"
    _description = "Migrate Aabaan data into FM"

    migrate_visits = fields.Boolean(string="Migrate Visits as Work Orders", default=True)
    result_message = fields.Text(readonly=True)

    # ------------------------------------------------------------------
    def _get_category(self, service_type):
        line = SERVICE_LINE.get(service_type, "other")
        Cat = self.env["fm.asset.category"]
        name = "Migrated — %s" % dict(Cat._fields["service_line"].selection).get(line, line)
        cat = Cat.search([("name", "=", name)], limit=1)
        if not cat:
            cat = Cat.create({"name": name, "service_line": line, "default_criticality": "medium"})
        return cat

    def _get_location(self, company, emirate):
        Loc = self.env["fm.asset.location"]
        name = emirate or "Migrated Sites"
        loc = Loc.search([("name", "=", name), ("location_type", "=", "site")], limit=1)
        if not loc:
            loc = Loc.create({"name": name, "location_type": "site", "company_id": company.id})
        return loc

    def action_migrate(self):
        self.ensure_one()
        Contract = self.env["aabaan.service.contract"]
        FmContract = self.env["fm.contract"]
        FmAsset = self.env["fm.asset"]
        FmWo = self.env["fm.workorder"]

        n_contracts = n_assets = n_visits = 0

        for c in Contract.search([]):
            if FmContract.search_count([("aabaan_contract_id", "=", c.id)]):
                continue
            company = c.company_id or self.env.company

            asset = FmAsset.create({
                "name": "%s — %s" % (c.partner_id.display_name, c.area or c.name),
                "category_fm_id": self._get_category(c.service_type).id,
                "location_fm_id": self._get_location(company, c.emirate).id,
                "criticality": "medium",
                "company_id": company.id,
            })
            n_assets += 1

            fmc = FmContract.create({
                "partner_id": c.partner_id.id,
                "contract_type": "amc_comprehensive",
                "start_date": c.start_date,
                "end_date": c.end_date,
                "acv": c.contract_value,
                "account_manager_id": (c.salesperson_id or self.env.user).id,
                "visit_frequency": FREQUENCY.get(c.frequency, "monthly"),
                "preferred_technician_id": c.default_technician_ids[:1].id or False,
                "state": CONTRACT_STATE.get(c.state, "draft"),
                "auto_schedule": False,
                "asset_ids": [(6, 0, [asset.id])],
                "aabaan_contract_id": c.id,
            })
            n_contracts += 1

            if self.migrate_visits:
                wo_vals = []
                for v in c.visit_ids:
                    if FmWo.search_count([("aabaan_visit_id", "=", v.id)]):
                        continue
                    start_dt = v.planned_start
                    if not start_dt and v.planned_date:
                        start_dt = datetime.combine(v.planned_date, time(9, 0))
                    stage = VISIT_STAGE.get(v.state, "draft")
                    if v.state == "done" and v.approved:
                        stage = "signed_off"
                    wo_vals.append({
                        "wo_type": "ppm",
                        "severity": "p3_medium",
                        "asset_id": asset.id,
                        "customer_id": c.partner_id.id,
                        "contract_id": fmc.id,
                        "company_id": company.id,
                        "technician_id": v.technician_ids[:1].id or False,
                        "stage": stage,
                        "problem_description": v.name or _("Migrated visit"),
                        "resolution_notes": v.after_notes or False,
                        "schedule_date_start": start_dt,
                        "schedule_date_end": v.planned_end or False,
                        "aabaan_visit_id": v.id,
                    })
                if wo_vals:
                    created = FmWo.create(wo_vals)
                    n_visits += len(created)

        self.result_message = _(
            "Migration complete: %(c)s contracts, %(a)s assets, %(v)s work orders created."
        ) % {"c": n_contracts, "a": n_assets, "v": n_visits}

        return {
            "type": "ir.actions.act_window",
            "res_model": "fm.aabaan.migration.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
