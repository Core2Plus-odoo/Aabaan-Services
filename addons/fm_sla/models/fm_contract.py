# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class FmContract(models.Model):
    """Nightly contract health scoring (brief §6.5). Writes the plain
    health_score / health_band fields defined in fm_contract.
    """

    _inherit = "fm.contract"

    def _band_for_score(self, score):
        if score < 4:
            return "critical"
        if score < 6:
            return "at_risk"
        if score < 8:
            return "watch"
        return "healthy"

    def _compute_fm_health(self):
        """Recompute health for the recordset from the last 90 days of WOs."""
        today = fields.Date.context_today(self)
        since = fields.Datetime.to_datetime(today - relativedelta(days=90))
        Wo = self.env["fm.workorder"]
        for contract in self:
            wos = Wo.search([("contract_id", "=", contract.id), ("create_date", ">=", since)])
            score = 10.0

            # SLA performance (40%)
            evaluated = wos.filtered(lambda w: w.sla_resolution_status in ("met", "breached"))
            if evaluated:
                met = len(evaluated.filtered(lambda w: w.sla_resolution_status == "met"))
                sla_pct = met / len(evaluated)
                score -= (1 - sla_pct) * 4

            # CSAT trend (20%)
            rated = wos.filtered(lambda w: w.csat_rating)
            if rated:
                avg_csat = sum(int(w.csat_rating) for w in rated) / len(rated)
                score -= (5 - avg_csat) * 0.4

            # Open critical issues (20%)
            open_crit = len(wos.filtered(
                lambda w: w.severity in ("p1_critical", "p2_high")
                and w.stage not in ("signed_off", "cancelled")
            ))
            score -= min(open_crit, 5) * 0.4

            score = max(0.0, min(10.0, score))
            contract.health_score = score
            contract.health_band = contract._band_for_score(score)

    @api.model
    def _cron_compute_contract_health(self):
        self.search([("state", "=", "active")])._compute_fm_health()
