# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

# Fields whose change should refresh the linked calendar event.
SYNC_FIELDS = {
    "schedule_date_start", "schedule_date_end", "technician_id",
    "stage", "asset_id", "name", "customer_id",
}


class FmWorkOrder(models.Model):
    """Sync scheduled work orders to the standard Odoo Calendar (brief §10)."""

    _inherit = "fm.workorder"

    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", readonly=True, copy=False)

    def _calendar_values(self):
        self.ensure_one()
        start = self.schedule_date_start
        stop = self.schedule_date_end or (start and start + timedelta(hours=1))
        partners = self.env["res.partner"]
        if self.technician_id.user_id:
            partners |= self.technician_id.user_id.partner_id
        if self.customer_id:
            partners |= self.customer_id
        return {
            "name": "%s — %s" % (self.name, self.asset_id.display_name),
            "start": start,
            "stop": stop,
            "partner_ids": [(6, 0, partners.ids)],
            "user_id": self.technician_id.user_id.id or self.env.uid,
        }

    def _sync_calendar_event(self):
        Event = self.env["calendar.event"]
        for wo in self:
            # No date or terminal stage -> drop any existing event
            if not wo.schedule_date_start or wo.stage in ("cancelled", "signed_off"):
                if wo.calendar_event_id:
                    wo.calendar_event_id.unlink()
                continue
            vals = wo._calendar_values()
            if wo.calendar_event_id:
                wo.calendar_event_id.write(vals)
            else:
                wo.calendar_event_id = Event.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.with_context(fm_skip_calendar=True)._sync_calendar_event()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("fm_skip_calendar") and SYNC_FIELDS & set(vals):
            self.with_context(fm_skip_calendar=True)._sync_calendar_event()
        return res
