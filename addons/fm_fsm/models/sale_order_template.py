# -*- coding: utf-8 -*-
from odoo import fields, models

from .fm_visit_schedule_mixin import FREQUENCY_SELECTION, TIME_SLOTS


class SaleOrderTemplate(models.Model):
    """The visit schedule half of a contract profile.

    fm_contract puts the commercial profile on the quotation template
    (service, term, billing); this adds the cadence, because the fields it
    mirrors live on fm.visit.schedule.mixin, which is this module's.

    Separate module, same template: a pest control AMC is sold on a fixed
    cadence, so the template that carries its price should carry how often
    somebody turns up too.
    """

    _inherit = "sale.order.template"

    fm_visit_frequency = fields.Selection(
        FREQUENCY_SELECTION, string="Visit Frequency", default="monthly",
    )
    fm_custom_interval_days = fields.Integer(
        string="Custom Interval (days)",
        help="Used when Visit Frequency is 'Custom'.",
    )
    fm_visit_day_1 = fields.Integer(string="1st Visit Day", default=1)
    fm_visit_day_2 = fields.Integer(string="2nd Visit Day", default=15)
    fm_time_slot = fields.Selection(
        TIME_SLOTS, string="Visit Time Slot", default="morning",
    )
    fm_visit_duration_hours = fields.Float(
        string="Default Visit Duration (hours)", default=2.0,
    )
    fm_skip_weekends = fields.Boolean(string="Skip Weekends", default=True)
