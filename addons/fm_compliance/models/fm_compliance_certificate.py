# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

EXPIRING_SOON_DAYS = 30


class FmComplianceCertificate(models.Model):
    """A compliance certificate for an asset or location (brief §5.6).

    The daily watchdog (§6.6) raises a compliance work order ahead of expiry
    and flags expired certificates.
    """

    _name = "fm.compliance.certificate"
    _description = "FM Compliance Certificate"
    _order = "expiry_date"

    name = fields.Char(compute="_compute_name", store=True)
    asset_id = fields.Many2one("fm.asset", index=True)
    location_id = fields.Many2one("fm.asset.location", index=True)
    regime_id = fields.Many2one("fm.compliance.regime", required=True, index=True)
    certificate_number = fields.Char()
    issued_by = fields.Char()
    issue_date = fields.Date(required=True)
    expiry_date = fields.Date(required=True, index=True)
    state = fields.Selection(
        [
            ("valid", "Valid"),
            ("expiring_soon", "Expiring Soon"),
            ("expired", "Expired"),
            ("renewed", "Renewed"),
        ],
        compute="_compute_state",
        store=True,
    )
    document_attachment_id = fields.Many2one("ir.attachment")
    related_workorder_id = fields.Many2one("project.task", readonly=True, string="Remediation Work Order")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("regime_id", "certificate_number", "asset_id", "location_id")
    def _compute_name(self):
        for cert in self:
            target = cert.asset_id.display_name or cert.location_id.display_name or ""
            cert.name = "%s — %s" % (cert.regime_id.name or "Certificate", cert.certificate_number or target or "")

    @api.depends("expiry_date")
    def _compute_state(self):
        today = fields.Date.context_today(self)
        soon = today + relativedelta(days=EXPIRING_SOON_DAYS)
        for cert in self:
            if not cert.expiry_date:
                cert.state = "valid"
            elif cert.expiry_date < today:
                cert.state = "expired"
            elif cert.expiry_date <= soon:
                cert.state = "expiring_soon"
            else:
                cert.state = "valid"

    def _create_compliance_workorder(self):
        self.ensure_one()
        asset = self.asset_id
        company = asset.company_id if asset else self.company_id
        project = self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)
        vals = {
            "name": "Compliance renewal — %s" % (self.regime_id.name or ""),
            "company_id": company.id,
            "partner_id": company.partner_id.id,
            "fm_asset_id": asset.id if asset else False,
            "fm_wo_type": "compliance",
            "fm_severity": "p2_high",
            "description": "Compliance renewal due: %s (expires %s)"
            % (self.regime_id.name, self.expiry_date),
        }
        if project:
            vals["project_id"] = project.id
        task = self.env["project.task"].create(vals)
        self.related_workorder_id = task.id
        return task

    @api.model
    def _cron_certificate_watchdog(self):
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(days=EXPIRING_SOON_DAYS)
        certs = self.search(
            [
                ("state", "!=", "renewed"),
                ("expiry_date", "<=", horizon),
            ]
        )
        for cert in certs:
            if cert.asset_id and not (
                cert.related_workorder_id
                and cert.related_workorder_id.stage not in ("signed_off", "cancelled")
            ):
                cert._create_compliance_workorder()
