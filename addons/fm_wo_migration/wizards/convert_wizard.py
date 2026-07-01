# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

# Legacy fm.workorder.stage -> fm_fsm project.task.type external id.
STAGE_MAP = {
    "draft": "fm_fsm.fsm_stage_draft",
    "assigned": "fm_fsm.fsm_stage_assigned",
    "acknowledged": "fm_fsm.fsm_stage_acknowledged",
    "arrived": "fm_fsm.fsm_stage_in_progress",
    "in_progress": "fm_fsm.fsm_stage_in_progress",
    "awaiting_parts": "fm_fsm.fsm_stage_in_progress",
    "awaiting_customer": "fm_fsm.fsm_stage_in_progress",
    "completed": "fm_fsm.fsm_stage_completed",
    "signed_off": "fm_fsm.fsm_stage_signed_off",
    "cancelled": "fm_fsm.fsm_stage_cancelled",
}


class FmWoConvertWizard(models.TransientModel):
    _name = "fm.wo.convert.wizard"
    _description = "Convert legacy fm.workorder rows into native FSM tasks"

    result_message = fields.Text(readonly=True)

    def _table_exists(self):
        self.env.cr.execute("SELECT to_regclass('public.fm_workorder')")
        return self.env.cr.fetchone()[0] is not None

    def action_convert(self):
        self.ensure_one()
        if not self._table_exists():
            raise UserError(_(
                "No legacy 'fm_workorder' table found. Either the data was already "
                "migrated and the module uninstalled, or there was nothing to convert."
            ))

        Task = self.env["project.task"]
        project = self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)
        stage_cache = {}

        def stage_id(code):
            if code not in stage_cache:
                rec = self.env.ref(STAGE_MAP.get(code, "fm_fsm.fsm_stage_draft"),
                                   raise_if_not_found=False)
                stage_cache[code] = rec.id if rec else False
            return stage_cache[code]

        # Only convert columns that are guaranteed to exist on the legacy model.
        self.env.cr.execute("""
            SELECT id, name, wo_type, severity, stage, asset_id, contract_id,
                   customer_id, company_id, technician_id,
                   problem_description, resolution_notes, schedule_date_start
              FROM fm_workorder
             ORDER BY id
        """)
        rows = self.env.cr.dictfetchall()

        # Skip rows already converted (idempotent re-run).
        done = set(
            Task.search([("legacy_workorder_id", "!=", False)]).mapped("legacy_workorder_id")
        )
        # Employee -> user resolution.
        Emp = self.env["hr.employee"]

        created = 0
        skipped = 0
        for r in rows:
            if r["id"] in done:
                skipped += 1
                continue
            desc = r.get("problem_description") or ""
            if r.get("resolution_notes"):
                desc = "%s\n\n%s" % (desc, r["resolution_notes"])
            deadline = r.get("schedule_date_start")
            vals = {
                "name": r.get("name") or _("Migrated work order"),
                "company_id": r.get("company_id") or self.env.company.id,
                "partner_id": r.get("customer_id") or False,
                "fm_asset_id": r.get("asset_id") or False,
                "fm_contract_id": r.get("contract_id") or False,
                "fm_wo_type": r.get("wo_type") or "reactive",
                "fm_severity": r.get("severity") or "p3_medium",
                "description": desc or False,
                "date_deadline": deadline.date() if deadline else False,
                "legacy_workorder_id": r["id"],
            }
            if project:
                vals["project_id"] = project.id
            sid = stage_id(r.get("stage") or "draft")
            if sid:
                vals["stage_id"] = sid
            if r.get("technician_id"):
                user = Emp.browse(r["technician_id"]).user_id
                if user:
                    vals["user_ids"] = [(6, 0, [user.id])]
            Task.create(vals)
            created += 1

        self.result_message = _(
            "Converted %(c)s legacy work order(s) into Field Service tasks. "
            "%(s)s already converted (skipped).\n\n"
            "You can now uninstall fm_workorder, fm_ppm, fm_sla and fm_integrations "
            "from Apps, then uninstall this converter."
        ) % {"c": created, "s": skipped}

        return {
            "type": "ir.actions.act_window",
            "res_model": "fm.wo.convert.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
