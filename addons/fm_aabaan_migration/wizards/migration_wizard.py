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

# Map aabaan visit state to the fm_fsm project.task.type external id.
VISIT_STAGE = {
    "draft": "fm_fsm.fsm_stage_draft",
    "scheduled": "fm_fsm.fsm_stage_assigned",
    "in_progress": "fm_fsm.fsm_stage_in_progress",
    "done": "fm_fsm.fsm_stage_completed",
    "missed": "fm_fsm.fsm_stage_cancelled",
    "cancelled": "fm_fsm.fsm_stage_cancelled",
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
        Task = self.env["project.task"]
        project = self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)

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

            # Carry the contract's service product onto the FM contract as a
            # recurring order line (reuses the existing product.product), so
            # subscription billing has something to invoice.
            if c.product_id:
                self.env["sale.order.line"].create({
                    "order_id": fmc.sale_order_id.id,
                    "product_id": c.product_id.id,
                    "name": c.product_id.display_name,
                    "product_uom_qty": 1.0,
                    "price_unit": c.billing_cycle_amount or c.contract_value or 0.0,
                })

            if self.migrate_visits:
                task_vals = []
                for v in c.visit_ids:
                    if Task.search_count([("aabaan_visit_id", "=", v.id)]):
                        continue
                    start_dt = v.planned_start
                    if not start_dt and v.planned_date:
                        start_dt = datetime.combine(v.planned_date, time(9, 0))
                    stage_xmlid = VISIT_STAGE.get(v.state, "fm_fsm.fsm_stage_draft")
                    if v.state == "done" and v.approved:
                        stage_xmlid = "fm_fsm.fsm_stage_signed_off"
                    stage = self.env.ref(stage_xmlid, raise_if_not_found=False)
                    tech = v.technician_ids[:1]
                    tech_user = tech.user_id if tech and tech.user_id else False
                    notes = v.name or _("Migrated visit")
                    if v.after_notes:
                        notes = "%s\n%s" % (notes, v.after_notes)
                    vals = {
                        "name": v.name or _("Migrated visit"),
                        "company_id": company.id,
                        "partner_id": c.partner_id.id,
                        "fm_asset_id": asset.id,
                        "fm_contract_id": fmc.id,
                        "fm_wo_type": "ppm",
                        "fm_severity": "p3_medium",
                        "description": notes,
                        "date_deadline": start_dt.date() if start_dt else False,
                        "aabaan_visit_id": v.id,
                    }
                    if project:
                        vals["project_id"] = project.id
                    if stage:
                        vals["stage_id"] = stage.id
                    if tech_user:
                        vals["user_ids"] = [(6, 0, [tech_user.id])]
                    task_vals.append(vals)
                if task_vals:
                    created = Task.create(task_vals)
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
