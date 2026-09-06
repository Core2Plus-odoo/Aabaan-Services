# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Tabs of the Executive Command Centre, in the order the client approved.
TABS = [
    ('executive', 'Executive Overview'),
    ('field', 'Field Operations'),
    ('sales', 'Sales & CRM'),
    ('finance', 'Finance'),
    ('expenses', 'Expenses & Margin'),
    ('cash', 'Cash & Bank'),
    ('amc', 'AMC & Renewals'),
]

# Period selector. Every period-scoped figure on screen is bounded by the
# selected window, and compared against the immediately preceding window of
# the same length — so a delta is always like-for-like.
PERIODS = [
    ('this_month', 'This month'),
    ('last_month', 'Last month'),
    ('quarter', 'This quarter'),
    ('ytd', 'Year to date'),
    ('last_12m', 'Last 12 months'),
]

# Reading raw check-in/check-out pairs to average time on site: the duration
# field is computed, not stored, so it cannot be summed by the database. This
# caps how many rows are pulled back for that one average.
DURATION_SAMPLE_CAP = 8000

# The same business fact is spelled differently on the two Aabaan platforms.
# On the FM build the contract is a sale.order carrying fm_service_line,
# fm_end_date and a branch, and a visit points back at it through
# fm_contract_order_id; on the aabaan build those same facts live in manual
# x_* fields defined in the database. Neither set can simply be imported into
# the other -- one is code the other build does not have, the other is data
# this build does not have.
#
# So the dashboard asks for a *concept* and takes the first spelling that
# actually exists here. A concept nothing answers collapses its own section,
# which is what a missing field already did; this only widens what counts as
# an answer. It also means the fm_end_date/end_date duplication can be
# resolved later without touching this file.
FIELD_ALIASES = {
    ('sale.order', 'service_line'): ('fm_service_line', 'x_service_line'),
    ('sale.order', 'branch'): ('branch_id', 'x_emirate_regime'),
    ('sale.order', 'contract_end'): ('fm_end_date', 'end_date'),
    ('project.task', 'service_line'): ('fm_service_line', 'x_service_line'),
    ('project.task', 'visit_type'): ('fm_wo_type', 'x_visit_type'),
    ('project.task', 'contract'): ('fm_contract_order_id', 'sale_order_id'),
    ('project.task', 'deadline'): ('x_sla_due', 'date_deadline'),
    ('account.move', 'service_line'): ('aabaan_services',),
}

# Compliance documents, as (model, expiry date field). First one present wins.
COMPLIANCE_SOURCES = (
    ('fm.compliance.certificate', 'expiry_date'),
    ('aabaan.contract.document', 'valid_until'),
)


class FmCommandCentre(models.AbstractModel):
    """Data provider for the Command Centre client action.

    Seven tabs, each loaded on demand — the client asks for one tab at a
    time, so opening the dashboard never runs the queries for screens the
    user isn't looking at.

    Three rules hold everywhere in this file:

    1. Aggregation is batched through ``_read_group`` / ``search_count``.
       No per-record Python loops over contracts or invoices.
    2. Platform fields are resolved at runtime, through ``_field`` and the
       alias table above. Some are manual (Studio) fields that exist only in
       a database; some belong to sibling modules that may not be installed.
       Every one is guarded: a concept nothing answers collapses its section
       into an honest empty state rather than raising.
    3. No figure is estimated. Where a number cannot be derived from real
       records it is left out, and the reason is stated on screen.

    Note on the contract cockpit: ``cockpit_*`` fields are computed and NOT
    stored, so they cannot be grouped or filtered in a domain. The
    at-risk contract signals below are therefore rebuilt from the same
    underlying records (visits, end dates) via batched queries.
    """
    _name = 'fm.command.centre'
    _description = 'FM Command Centre data provider'

    # ------------------------------------------------------------------
    # periods
    # ------------------------------------------------------------------

    @api.model
    def _period_bounds(self, period):
        """(start, end, previous_start, previous_end) as dates; end is
        exclusive. The previous window is always the same length as the
        current one, so every delta compares like with like."""
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        if period == 'last_month':
            start = month_start - relativedelta(months=1)
            end = month_start
        elif period == 'quarter':
            start = month_start - relativedelta(
                months=(today.month - 1) % 3)
            end = start + relativedelta(months=3)
        elif period == 'ytd':
            start = today.replace(month=1, day=1)
            end = today + timedelta(days=1)
        elif period == 'last_12m':
            start = month_start - relativedelta(months=11)
            end = month_start + relativedelta(months=1)
        else:  # this_month
            start = month_start
            end = month_start + relativedelta(months=1)
        span = end - start
        return start, end, start - span, start

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @api.model
    def _selection_labels(self, model, fname):
        info = self.env[model].fields_get([fname], ['selection']).get(fname) or {}
        return dict(info.get('selection') or [])

    @api.model
    def _sums(self, model, domain, aggregates):
        rows = self.env[model]._read_group(domain, [], aggregates)
        row = rows[0] if rows else tuple(None for _a in aggregates)
        return [value or 0 for value in row]

    @api.model
    def _metric(self, label, model, domain, aggregates=None, **extra):
        """One drillable figure: a label, the number(s), and the exact
        domain that produced it — so every tile on screen is one click
        from the records behind it. The key is derived from the label so
        the client always has a stable, unique list key to render with."""
        out = {
            'key': ''.join(
                ch if ch.isalnum() else '_' for ch in label.casefold()),
            'label': label, 'model': model, 'domain': domain,
        }
        if aggregates:
            values = self._sums(model, domain, aggregates)
            out['gross'] = values[0]
            out['count'] = values[-1] if len(values) > 1 else None
        else:
            out['count'] = self.env[model].search_count(domain)
        out.update(extra)
        return out

    @api.model
    def _delta(self, current, previous):
        """Percentage change against the previous window, or None when
        there is no baseline. An undefined delta renders blank — never as
        0% or 100%, which would both read as facts."""
        if not previous:
            return None
        return round(100.0 * (current - previous) / abs(previous), 1)

    @api.model
    def _pct(self, part, whole, digits=1):
        return round(100.0 * part / whole, digits) if whole else None

    @api.model
    def _months(self, model, domain_fn, aggregates, months=12):
        """A month-by-month series ending with the current month."""
        month_start = fields.Date.context_today(self).replace(day=1)
        out = []
        for offset in range(-(months - 1), 1):
            m_from = month_start + relativedelta(months=offset)
            m_to = m_from + relativedelta(months=1)
            domain = domain_fn(m_from, m_to)
            gross, count = self._sums(model, domain, aggregates)
            out.append({
                'key': m_from.strftime('%Y-%m'),
                'label': m_from.strftime('%b'),
                'gross': gross, 'count': count,
                'model': model, 'domain': domain,
            })
        return out

    @api.model
    def _field(self, model, concept):
        """The first aliased spelling of ``concept`` that exists on ``model``
        in this database, or False when this build has none of them."""
        if model not in self.env:
            return False
        Model = self.env[model]
        for name in FIELD_ALIASES.get((model, concept), ()):
            if name in Model._fields:
                return name
        return False

    @api.model
    def _compliance_source(self):
        """(model, expiry field) for compliance documents on this build, or
        (False, False) when neither platform's model is installed."""
        for model, fname in COMPLIANCE_SOURCES:
            if model in self.env and fname in self.env[model]._fields:
                return model, fname
        return False, False

    @api.model
    def _field_values(self, model, fname):
        """[(domain value, label)] for a selection or many2one field, so a
        split reads the same whether the platform spells the concept as a
        selection of emirates or a link to a branch record."""
        field = self.env[model]._fields[fname]
        if field.type == 'many2one':
            return [(rec.id, rec.display_name)
                    for rec in self.env[field.comodel_name].search([])]
        return list(self._selection_labels(model, fname).items())

    @api.model
    def _group_amounts(self, model, base_domain, fname):
        """Gross/count grouped by a (possibly manual) selection field."""
        Model = self.env[model]
        if not fname or fname not in Model._fields:
            return []
        field = Model._fields[fname]
        is_m2o = field.type == 'many2one'
        # _read_group hands back a record for a many2one and a raw value for a
        # selection; str() on a record would put "fm.branch(3,)" in the key.
        labels = {} if is_m2o else self._selection_labels(model, fname)
        out = []
        for value, total, count in Model._read_group(
                base_domain, [fname], ['amount_total:sum', '__count']):
            out.append({
                'key': (str(value.id) if value else 'none') if is_m2o
                       else str(value or 'none'),
                'label': (value.display_name if value else 'Not set') if is_m2o
                         else labels.get(value, value or 'Not set'),
                'gross': total or 0.0,
                'count': count,
                'model': model,
                'domain': base_domain + [
                    (fname, '=', (value.id if value else False) if is_m2o
                                 else value)],
            })
        out.sort(key=lambda item: -item['gross'])
        return out

    # ------------------------------------------------------------------
    # shared domains
    # ------------------------------------------------------------------

    @api.model
    def _book_domain(self):
        return [('state', '=', 'sale')]

    @api.model
    def _invoice_domain(self):
        return [('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')]

    @api.model
    def _fsm_domain(self):
        return [('project_id.is_fsm', '=', True)]

    @api.model
    def _ar_domain(self):
        return [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial'))]

    @api.model
    def _expense_line_domain(self, start=None, end=None):
        """Posted lines on an expense account.

        Account type, not move type: a payroll journal entry is a cost even
        though it is not a vendor bill. In Odoo 19 the ``expense`` prefix
        covers expense, expense_depreciation and expense_direct_cost.
        """
        domain = [('parent_state', '=', 'posted'),
                  ('account_id.account_type', 'like', 'expense')]
        if start is not None:
            domain.append(('date', '>=', fields.Date.to_string(start)))
        if end is not None:
            domain.append(('date', '<', fields.Date.to_string(end)))
        return domain

    @api.model
    def _cash_journals(self):
        return self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash'))])

    @api.model
    def _cash_line_domain(self, start=None, end=None):
        """Posted lines sitting on a bank or cash journal's own account —
        the movements that actually change the balance."""
        accounts = self._cash_journals().mapped('default_account_id')
        if not accounts:
            return None
        domain = [('account_id', 'in', accounts.ids),
                  ('parent_state', '=', 'posted')]
        if start is not None:
            domain.append(('date', '>=', fields.Date.to_string(start)))
        if end is not None:
            domain.append(('date', '<', fields.Date.to_string(end)))
        return domain

    @api.model
    def _emirate_plan(self):
        """The Emirate analytic plan, resolved by name (Rule 2 — it is
        defined in the database, not in the source). Returns an empty
        recordset when the plan does not exist, so the branch split
        collapses into an honest empty state rather than raising."""
        Plan = self.env['account.analytic.plan']
        return Plan.search([('name', 'ilike', 'emirate')], limit=1)

    @api.model
    def _payment_domain(self, start, end):
        return [('payment_type', '=', 'inbound'),
                ('state', 'in', ('posted', 'paid', 'in_process')),
                ('date', '>=', fields.Date.to_string(start)),
                ('date', '<', fields.Date.to_string(end))]

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    @api.model
    def get_data(self, tab='executive', period='this_month'):
        if tab not in dict(TABS):
            tab = 'executive'
        if period not in dict(PERIODS):
            period = 'this_month'
        start, end, prev_start, prev_end = self._period_bounds(period)
        company = self.env.company
        data = {
            'company': company.name,
            'currency': (company.currency_id.symbol
                         or company.currency_id.name or 'AED'),
            'as_of': fields.Datetime.to_string(fields.Datetime.now()),
            'tab': tab,
            'period': period,
            'period_label': dict(PERIODS)[period],
            'tabs': [{'key': key, 'label': label} for key, label in TABS],
            'periods': [{'key': key, 'label': label} for key, label in PERIODS],
            'range': '%s → %s' % (start.strftime('%d %b %Y'),
                                  (end - timedelta(days=1)).strftime('%d %b %Y')),
        }
        handler = getattr(self, '_tab_%s' % tab)
        data.update(handler(start, end, prev_start, prev_end))
        return data

    # ------------------------------------------------------------------
    # tab 1 — Executive Overview
    # ------------------------------------------------------------------

    def _tab_executive(self, start, end, prev_start, prev_end):
        book = self._book_domain()
        gross, net, count = self._sums(
            'sale.order', book,
            ['amount_total:sum', 'amount_untaxed:sum', '__count'])

        tiles = [dict(self._metric(
            'Contracted book', 'sale.order', book,
            ['amount_total:sum', '__count']), net=net, hero=True)]
        tiles.append(self._metric(
            'Open quotations', 'sale.order',
            [('state', 'in', ('draft', 'sent'))],
            ['amount_total:sum', '__count']))
        if 'crm.lead' in self.env:
            tiles.append(self._metric(
                'Sales pipeline', 'crm.lead',
                ['|', ('stage_id', '=', False), ('stage_id.is_won', '=', False)],
                ['expected_revenue:sum', '__count']))
        ar_domain = self._ar_domain()
        residual, ar_count = self._sums(
            'account.move', ar_domain, ['amount_residual:sum', '__count'])
        overdue_domain = ar_domain + [
            ('invoice_date_due', '<', fields.Date.to_string(
                fields.Date.context_today(self)))]
        overdue, overdue_count = self._sums(
            'account.move', overdue_domain, ['amount_residual:sum', '__count'])
        tiles.append({
            'label': 'Receivables outstanding', 'gross': residual,
            'count': ar_count, 'model': 'account.move', 'domain': ar_domain,
            'sub_gross': overdue, 'sub_count': overdue_count,
            'sub_label': 'overdue', 'sub_domain': overdue_domain,
        })
        tiles.append(self._metric(
            'Customers', 'res.partner', [('customer_rank', '>', 0)]))

        # period block, each figure beside the same-length previous window
        def period_pair(label, model, domain_fn, aggregates):
            cur = domain_fn(start, end)
            prv = domain_fn(prev_start, prev_end)
            c_gross, c_count = self._sums(model, cur, aggregates)
            p_gross, p_count = self._sums(model, prv, aggregates)
            return {
                'label': label, 'model': model, 'domain': cur,
                'gross': c_gross, 'count': c_count,
                'prev_gross': p_gross, 'prev_count': p_count,
                'delta': self._delta(c_gross, p_gross),
            }

        period_block = [
            period_pair(
                'New contracts signed', 'sale.order',
                lambda s, e: [('state', '=', 'sale'),
                              ('date_order', '>=', fields.Date.to_string(s)),
                              ('date_order', '<', fields.Date.to_string(e))],
                ['amount_total:sum', '__count']),
            period_pair(
                'Invoiced, net of VAT', 'account.move',
                lambda s, e: self._invoice_domain() + [
                    ('invoice_date', '>=', fields.Date.to_string(s)),
                    ('invoice_date', '<', fields.Date.to_string(e))],
                ['amount_untaxed_signed:sum', '__count']),
            period_pair(
                'Cash collected', 'account.payment',
                lambda s, e: self._payment_domain(s, e),
                ['amount:sum', '__count']),
        ]
        if 'crm.lead' in self.env:
            period_block.append(period_pair(
                'New leads', 'crm.lead',
                lambda s, e: [('create_date', '>=', fields.Date.to_string(s)),
                              ('create_date', '<', fields.Date.to_string(e))],
                ['expected_revenue:sum', '__count']))

        top_customers = []
        rows = self.env['sale.order']._read_group(
            book, ['partner_id'], ['amount_total:sum', '__count'])
        rows.sort(key=lambda row: -(row[1] or 0.0))
        for partner, total, cnt in rows[:8]:
            top_customers.append({
                'key': str(partner.id), 'label': partner.name,
                'gross': total or 0.0, 'count': cnt,
                'share': self._pct(total or 0.0, gross) or 0.0,
                'model': 'sale.order',
                'domain': book + [('partner_id', '=', partner.id)],
            })

        # Exception strip — the dashboard leads with what needs action.
        # Every entry is a live count carrying its drill-down domain;
        # anything with nothing to report is dropped, so a quiet business
        # shows a quiet strip rather than a row of zeros.
        today = fields.Date.context_today(self)
        today_s = fields.Date.to_string(today)
        exceptions = []

        def exc(key, label, model, domain, aggregates=None,
                status='critical'):
            if aggregates:
                total, cnt = self._sums(model, domain, aggregates)
            else:
                total, cnt = None, self.env[model].search_count(domain)
            if cnt:
                entry = {'key': key, 'label': label, 'count': cnt,
                         'status': status, 'model': model, 'domain': domain}
                if total is not None:
                    entry['gross'] = total
                exceptions.append(entry)

        exc('ar90', 'receivables overdue 90+ days', 'account.move',
            self._ar_domain() + [('invoice_date_due', '<',
                                  fields.Date.to_string(
                                      today - timedelta(days=90)))],
            ['amount_residual:sum', '__count'])
        end_field = self._field('sale.order', 'contract_end')
        if end_field:
            exc('pastterm', 'contracts past end-of-term', 'sale.order',
                self._book_domain() + [(end_field, '!=', False),
                                       (end_field, '<', today_s)],
                ['amount_total:sum', '__count'])
        Task = self.env['project.task']
        open_fsm = self._fsm_domain() + [('stage_id.fold', '=', False)]
        due_field = self._field('project.task', 'deadline')
        if due_field:
            exc('sla', 'visits past their deadline, still open',
                'project.task',
                open_fsm + [(due_field, '!=', False),
                            (due_field, '<', fields.Datetime.to_string(
                                fields.Datetime.now()))])
        if 'sla_escalated' in Task._fields:
            exc('esc', 'escalated visits still open', 'project.task',
                open_fsm + [('sla_escalated', '=', True)])
        doc_model, doc_field = self._compliance_source()
        if doc_model:
            exc('docs', 'compliance documents expired', doc_model,
                [(doc_field, '!=', False),
                 (doc_field, '<', today_s)])
        Company = self.env['res.company']
        if 'aabaan_licence_expiry' in Company._fields:
            exc('licence', 'trade licences expired or expiring in 60 days',
                'res.company',
                [('aabaan_licence_expiry', '!=', False),
                 ('aabaan_licence_expiry', '<', fields.Date.to_string(
                     today + timedelta(days=60)))],
                status='warning')

        return {
            'exceptions': exceptions,
            'tiles': tiles,
            'period_block': period_block,
            'revenue_months': self._months(
                'account.move',
                lambda s, e: self._invoice_domain() + [
                    ('invoice_date', '>=', fields.Date.to_string(s)),
                    ('invoice_date', '<', fields.Date.to_string(e))],
                ['amount_untaxed_signed:sum', '__count']),
            'collections_months': self._months(
                'account.payment',
                lambda s, e: self._payment_domain(s, e),
                ['amount:sum', '__count']),
            'top_customers': top_customers,
            'service_lines': self._group_amounts(
                'sale.order', book, self._field('sale.order', 'service_line')),
            'emirates': self._group_amounts(
                'sale.order', book, self._field('sale.order', 'branch')),
        }

    # ------------------------------------------------------------------
    # tab 2 — Field Operations
    # ------------------------------------------------------------------

    def _tab_field(self, start, end, prev_start, prev_end):
        Task = self.env['project.task']
        fsm = self._fsm_domain()
        open_domain = fsm + [('stage_id.fold', '=', False)]
        now = fields.Datetime.now()
        now_s = fields.Datetime.to_string(now)
        has_completed = 'visit_completed_at' in Task._fields
        has_followup = 'followup_task_id' in Task._fields
        has_sla = 'sla_escalated' in Task._fields
        has_planned = 'planned_date_begin' in Task._fields

        start_s = fields.Datetime.to_string(
            fields.Datetime.to_datetime(start))
        end_s = fields.Datetime.to_string(fields.Datetime.to_datetime(end))

        def in_period(field):
            return [(field, '>=', start_s), (field, '<', end_s)]

        kpis, notes = [], []

        # Visits completed in the period — the delivery volume.
        completed_domain = prev_completed = None
        if has_completed:
            completed_domain = fsm + [('visit_completed_at', '!=', False)] \
                + in_period('visit_completed_at')
            prev_completed = fsm + [('visit_completed_at', '!=', False)] + [
                ('visit_completed_at', '>=', fields.Datetime.to_string(
                    fields.Datetime.to_datetime(prev_start))),
                ('visit_completed_at', '<', start_s)]
            done = Task.search_count(completed_domain)
            prev_done = Task.search_count(prev_completed)
            kpis.append({
                'label': 'Visits completed', 'count': done,
                'delta': self._delta(done, prev_done),
                'prev_count': prev_done,
                'model': 'project.task', 'domain': completed_domain,
                'hero': True,
            })

            # First-time fix: a completed visit that did NOT need a
            # follow-up. The follow-up link is written by the field-ops
            # completion flow, so this is a real outcome, not a proxy.
            if has_followup:
                needed = Task.search_count(
                    completed_domain + [('followup_task_id', '!=', False)])
                kpis.append({
                    'label': 'First-time fix rate',
                    'pct': self._pct(done - needed, done),
                    'count': done - needed, 'of': done,
                    'model': 'project.task',
                    'domain': completed_domain + [
                        ('followup_task_id', '=', False)],
                    'note': '%s of %s completed visits closed without a '
                            'follow-up' % (done - needed, done),
                })
            else:
                notes.append('First-time fix rate needs the field-ops '
                             'completion flow (a visit_completed_at stamp).')

            # Average time on site. The duration field is computed, not
            # stored, so it cannot be summed in SQL — the raw check-in /
            # check-out pairs are read back and averaged here, capped. The
            # same recordset is reused for the per-technician hours below,
            # so this is one query, not two.
            sample = Task.search(
                completed_domain + [('visit_started_at', '!=', False)],
                limit=DURATION_SAMPLE_CAP)
            spans = [
                (task.visit_completed_at - task.visit_started_at)
                .total_seconds() / 3600.0
                for task in sample
                if task.visit_completed_at and task.visit_started_at]
            if spans:
                kpis.append({
                    'label': 'Average time on site',
                    'value': '%.1f h' % (sum(spans) / len(spans)),
                    'note': 'across %s visits with a check-in and check-out'
                            % len(spans),
                })
                if len(sample) == DURATION_SAMPLE_CAP:
                    notes.append(
                        'Time-on-site figures sampled from the most recent '
                        '%s visits.' % DURATION_SAMPLE_CAP)
        else:
            notes.append('Visit completion metrics need a visit_completed_at '
                         'stamp on the task.')

        # SLA: escalations raised against visits planned in the period.
        if has_sla and has_planned:
            planned_domain = fsm + in_period('planned_date_begin')
            planned = Task.search_count(planned_domain)
            escalated = Task.search_count(
                planned_domain + [('sla_escalated', '=', True)])
            kpis.append({
                'label': 'SLA clean',
                'pct': self._pct(planned - escalated, planned),
                'count': planned - escalated, 'of': planned,
                'model': 'project.task',
                'domain': planned_domain + [('sla_escalated', '=', True)],
                'note': '%s of %s visits planned in this window were never '
                        'escalated' % (planned - escalated, planned),
                'invert': True,
            })

        # Live attention cards — always "as of now", never period-bound,
        # because an overdue visit is overdue today regardless of filter.
        cards = []
        if has_planned:
            cards.append(self._metric(
                'Past planned date, still open', 'project.task',
                open_domain + [('planned_date_begin', '<', now_s)],
                status='critical'))
            cards.append(self._metric(
                'Scheduled, next 7 days', 'project.task',
                open_domain + [
                    ('planned_date_begin', '>=', now_s),
                    ('planned_date_begin', '<=', fields.Datetime.to_string(
                        now + timedelta(days=7)))]))
            cards.append(self._metric(
                'Unassigned, next 7 days', 'project.task',
                open_domain + [
                    ('user_ids', '=', False),
                    ('planned_date_begin', '>=', now_s),
                    ('planned_date_begin', '<=', fields.Datetime.to_string(
                        now + timedelta(days=7)))],
                status='warning'))
        due_field = self._field('project.task', 'deadline')
        if due_field:
            cards.append(self._metric(
                'Deadline passed, still open', 'project.task',
                open_domain + [(due_field, '!=', False),
                               (due_field, '<', now_s)], status='critical'))
        if has_sla:
            cards.append(self._metric(
                'Escalated and still open', 'project.task',
                open_domain + [('sla_escalated', '=', True)],
                status='critical'))

        # Technicians — visits completed and real hours on site.
        # Deliberately no "utilisation %": that needs each technician's
        # contracted working hours, which this database does not reliably
        # carry, and a percentage against an assumed 8-hour day would be
        # an invented number.
        technicians = []
        if has_completed:
            hours_by_user = {}
            for task in sample:
                if not (task.visit_started_at and task.visit_completed_at):
                    continue
                span = (task.visit_completed_at - task.visit_started_at)\
                    .total_seconds() / 3600.0
                for user in task.user_ids:
                    hours_by_user[user.id] = hours_by_user.get(user.id, 0.0) + span
            for user, cnt in Task._read_group(
                    completed_domain, ['user_ids'], ['__count']):
                if not user:
                    continue
                technicians.append({
                    'key': str(user.id), 'label': user.name, 'count': cnt,
                    'hours': round(hours_by_user.get(user.id, 0.0), 1),
                    'open': Task.search_count(
                        open_domain + [('user_ids', 'in', user.id)]),
                    'model': 'project.task',
                    'domain': completed_domain + [('user_ids', 'in', user.id)],
                })
            technicians.sort(key=lambda item: -item['count'])
            technicians = technicians[:10]

        # Visit funnel by stage — where the open work actually sits.
        stages = []
        for stage, cnt in Task._read_group(open_domain, ['stage_id'], ['__count']):
            stages.append({
                'key': str(stage.id or 'none'),
                'label': stage.name or 'No stage', 'count': cnt,
                'model': 'project.task',
                'domain': open_domain + [('stage_id', '=', stage.id or False)],
            })
        stages.sort(key=lambda item: -item['count'])

        by_type = []
        type_field = self._field('project.task', 'visit_type')
        if type_field:
            labels = self._selection_labels('project.task', type_field)
            period_domain = (completed_domain if has_completed else fsm)
            for value, cnt in Task._read_group(
                    period_domain, [type_field], ['__count']):
                by_type.append({
                    'key': str(value or 'none'),
                    'label': labels.get(value, value or 'Untyped'),
                    'count': cnt, 'model': 'project.task',
                    'domain': period_domain + [(type_field, '=', value)],
                })
            by_type.sort(key=lambda item: -item['count'])

        emirates = []
        branch_field = self._field('sale.order', 'branch')
        contract_field = self._field('project.task', 'contract')
        if branch_field and contract_field:
            path = '%s.%s' % (contract_field, branch_field)
            for value, label in self._field_values('sale.order', branch_field):
                domain = fsm + [(path, '=', value)]
                cnt = Task.search_count(domain)
                if not cnt:
                    continue
                emirates.append({
                    'key': str(value), 'label': label, 'count': cnt,
                    'open': Task.search_count(open_domain + [(path, '=', value)]),
                    'model': 'project.task', 'domain': domain,
                })
            emirates.sort(key=lambda item: -item['count'])

        return {
            'kpis': kpis, 'cards': cards, 'technicians': technicians,
            'stages': stages, 'by_type': by_type, 'emirates': emirates,
            'notes': notes,
        }

    # ------------------------------------------------------------------
    # tab 3 — Sales & CRM
    # ------------------------------------------------------------------

    def _tab_sales(self, start, end, prev_start, prev_end):
        Sale = self.env['sale.order']
        start_s = fields.Date.to_string(start)
        end_s = fields.Date.to_string(end)
        prev_start_s = fields.Date.to_string(prev_start)

        kpis, notes = [], []

        signed_domain = [('state', '=', 'sale'),
                         ('date_order', '>=', start_s),
                         ('date_order', '<', end_s)]
        prev_signed = [('state', '=', 'sale'),
                       ('date_order', '>=', prev_start_s),
                       ('date_order', '<', start_s)]
        signed_gross, signed_count = self._sums(
            'sale.order', signed_domain, ['amount_total:sum', '__count'])
        prev_gross, prev_count = self._sums(
            'sale.order', prev_signed, ['amount_total:sum', '__count'])
        kpis.append({
            'label': 'Contracts signed', 'gross': signed_gross,
            'count': signed_count, 'prev_gross': prev_gross,
            'delta': self._delta(signed_gross, prev_gross),
            'model': 'sale.order', 'domain': signed_domain, 'hero': True,
        })

        quote_domain = [('state', 'in', ('draft', 'sent'))]
        q_gross, q_count = self._sums(
            'sale.order', quote_domain, ['amount_total:sum', '__count'])
        kpis.append({
            'label': 'Open quotations', 'gross': q_gross, 'count': q_count,
            'model': 'sale.order', 'domain': quote_domain,
        })

        # Quotation conversion: of the quotations raised in this window,
        # how many are now confirmed. Both sides counted on the same set
        # of records, so the ratio is real rather than two unrelated totals.
        raised = [('date_order', '>=', start_s), ('date_order', '<', end_s)]
        raised_count = Sale.search_count(raised)
        converted = Sale.search_count(raised + [('state', '=', 'sale')])
        kpis.append({
            'label': 'Quotation conversion',
            'pct': self._pct(converted, raised_count),
            'count': converted, 'of': raised_count,
            'model': 'sale.order', 'domain': raised + [('state', '=', 'sale')],
            'note': '%s of %s quotations raised in this window are confirmed'
                    % (converted, raised_count),
        })

        pipeline, sources, lost_reasons = [], [], []
        if 'crm.lead' in self.env:
            Lead = self.env['crm.lead']
            open_leads = ['|', ('stage_id', '=', False),
                          ('stage_id.is_won', '=', False)]
            p_gross, p_count = self._sums(
                'crm.lead', open_leads, ['expected_revenue:sum', '__count'])
            kpis.append({
                'label': 'Open pipeline', 'gross': p_gross, 'count': p_count,
                'model': 'crm.lead', 'domain': open_leads,
            })

            # Win rate over decided leads only. Lost leads are archived in
            # Odoo, so counting them needs active_test disabled — without
            # that the rate would silently read 100%.
            closed = [('create_date', '>=', fields.Datetime.to_string(
                fields.Datetime.to_datetime(start))),
                ('create_date', '<', fields.Datetime.to_string(
                    fields.Datetime.to_datetime(end)))]
            AllLeads = Lead.with_context(active_test=False)
            won = AllLeads.search_count(
                closed + [('active', '=', True), ('stage_id.is_won', '=', True)])
            lost = AllLeads.search_count(closed + [('active', '=', False)])
            decided = won + lost
            kpis.append({
                'label': 'Win rate',
                'pct': self._pct(won, decided),
                'count': won, 'of': decided,
                'model': 'crm.lead',
                'domain': closed + [('stage_id.is_won', '=', True)],
                'note': ('%s won of %s decided leads created in this window'
                         % (won, decided)) if decided else
                        'No leads created in this window have been decided yet',
            })

            for stage, total, cnt in Lead._read_group(
                    open_leads, ['stage_id'],
                    ['expected_revenue:sum', '__count']):
                pipeline.append({
                    'key': str(stage.id or 'none'),
                    'label': stage.name or 'No stage',
                    'gross': total or 0.0, 'count': cnt,
                    'sequence': stage.sequence or 0,
                    'model': 'crm.lead',
                    'domain': open_leads + [('stage_id', '=', stage.id or False)],
                })
            pipeline.sort(key=lambda item: item['sequence'])

            if 'source_id' in Lead._fields:
                for source, total, cnt in Lead._read_group(
                        closed, ['source_id'],
                        ['expected_revenue:sum', '__count']):
                    sources.append({
                        'key': str(source.id or 'none'),
                        'label': source.name or 'Source not set',
                        'gross': total or 0.0, 'count': cnt,
                        'model': 'crm.lead',
                        'domain': closed + [('source_id', '=', source.id or False)],
                    })
                sources.sort(key=lambda item: -item['count'])
                sources = sources[:8]

            if 'lost_reason_id' in Lead._fields:
                for reason, cnt in AllLeads._read_group(
                        closed + [('active', '=', False)],
                        ['lost_reason_id'], ['__count']):
                    lost_reasons.append({
                        'key': str(reason.id or 'none'),
                        'label': reason.name or 'Reason not recorded',
                        'count': cnt, 'model': 'crm.lead',
                        'domain': closed + [('active', '=', False),
                                            ('lost_reason_id', '=', reason.id or False)],
                    })
                lost_reasons.sort(key=lambda item: -item['count'])
                lost_reasons = lost_reasons[:6]
        else:
            notes.append('Pipeline, win rate and lead sources need the CRM app.')

        return {
            'kpis': kpis,
            'pipeline': pipeline,
            'sources': sources,
            'lost_reasons': lost_reasons,
            'signed_months': self._months(
                'sale.order',
                lambda s, e: [('state', '=', 'sale'),
                              ('date_order', '>=', fields.Date.to_string(s)),
                              ('date_order', '<', fields.Date.to_string(e))],
                ['amount_total:sum', '__count']),
            'service_lines': self._group_amounts(
                'sale.order', self._book_domain(),
                self._field('sale.order', 'service_line')),
            'size_bands': self._size_bands(),
            'notes': notes,
        }

    @api.model
    def _size_bands(self):
        book = self._book_domain()
        out = []
        for key, label, extra in (
                ('lt500', 'Below 500', [('amount_total', '<', 500)]),
                ('b500', '500 – 999',
                 [('amount_total', '>=', 500), ('amount_total', '<', 1000)]),
                ('b1k', '1,000 – 4,999',
                 [('amount_total', '>=', 1000), ('amount_total', '<', 5000)]),
                ('b5k', '5,000 – 19,999',
                 [('amount_total', '>=', 5000), ('amount_total', '<', 20000)]),
                ('b20k', '20,000 and above', [('amount_total', '>=', 20000)])):
            domain = book + extra
            gross, cnt = self._sums(
                'sale.order', domain, ['amount_total:sum', '__count'])
            out.append({'key': key, 'label': label, 'gross': gross,
                        'count': cnt, 'model': 'sale.order', 'domain': domain})
        return out

    # ------------------------------------------------------------------
    # tab 4 — Finance
    # ------------------------------------------------------------------

    def _tab_finance(self, start, end, prev_start, prev_end):
        Move = self.env['account.move']
        today = fields.Date.context_today(self)
        today_s = fields.Date.to_string(today)
        ar_domain = self._ar_domain()
        start_s = fields.Date.to_string(start)
        end_s = fields.Date.to_string(end)

        residual, ar_count = self._sums(
            'account.move', ar_domain, ['amount_residual:sum', '__count'])

        invoiced_domain = self._invoice_domain() + [
            ('invoice_date', '>=', start_s), ('invoice_date', '<', end_s)]
        invoiced, invoiced_count = self._sums(
            'account.move', invoiced_domain,
            ['amount_untaxed_signed:sum', '__count'])
        collected_domain = self._payment_domain(start, end)
        collected, collected_count = self._sums(
            'account.payment', collected_domain, ['amount:sum', '__count'])

        kpis = [
            {'label': 'Receivables outstanding', 'gross': residual,
             'count': ar_count, 'model': 'account.move', 'domain': ar_domain,
             'hero': True},
            {'label': 'Invoiced, net of VAT', 'gross': invoiced,
             'count': invoiced_count, 'model': 'account.move',
             'domain': invoiced_domain},
            {'label': 'Cash collected', 'gross': collected,
             'count': collected_count, 'model': 'account.payment',
             'domain': collected_domain},
        ]

        # Collection efficiency: cash collected against value invoiced in
        # the same window. Above 100% means older invoices were settled
        # too — which is why it is labelled as a ratio, not "% of invoices
        # paid".
        kpis.append({
            'label': 'Collection ratio',
            'pct': self._pct(collected, invoiced),
            'note': 'cash collected against value invoiced in this window; '
                    'above 100% means older invoices settled too',
        })

        # DSO — the standard receivables-days measure, with its inputs
        # named on screen so the number can be checked by hand.
        days = (end - start).days or 1
        dso = round(residual / invoiced * days, 1) if invoiced else None
        kpis.append({
            'label': 'Days sales outstanding',
            'value': ('%.1f days' % dso) if dso is not None else None,
            'note': 'receivables %s ÷ invoiced %s × %s days in window'
                    % (round(residual), round(invoiced), days),
        })

        # Ageing, measured from the due date. "Not yet due" is kept
        # separate from the overdue bands so the two are never conflated.
        ageing = []
        bands = [
            ('current', 'Not yet due', [('invoice_date_due', '>=', today_s)], None),
            ('d30', '1 – 30 days', [
                ('invoice_date_due', '<', today_s),
                ('invoice_date_due', '>=', fields.Date.to_string(
                    today - timedelta(days=30)))], 'warning'),
            ('d60', '31 – 60 days', [
                ('invoice_date_due', '<', fields.Date.to_string(
                    today - timedelta(days=30))),
                ('invoice_date_due', '>=', fields.Date.to_string(
                    today - timedelta(days=60)))], 'warning'),
            ('d90', '61 – 90 days', [
                ('invoice_date_due', '<', fields.Date.to_string(
                    today - timedelta(days=60))),
                ('invoice_date_due', '>=', fields.Date.to_string(
                    today - timedelta(days=90)))], 'critical'),
            ('d90p', 'Over 90 days', [
                ('invoice_date_due', '<', fields.Date.to_string(
                    today - timedelta(days=90)))], 'critical'),
        ]
        for key, label, extra, status in bands:
            domain = ar_domain + extra
            gross, cnt = self._sums(
                'account.move', domain, ['amount_residual:sum', '__count'])
            ageing.append({
                'key': key, 'label': label, 'gross': gross, 'count': cnt,
                'status': status, 'share': self._pct(gross, residual) or 0.0,
                'model': 'account.move', 'domain': domain,
            })

        # Recovery buckets are a stored field on this database (finance
        # core), so they group directly.
        recovery = []
        if 'recovery_bucket' in Move._fields:
            labels = self._selection_labels('account.move', 'recovery_bucket')
            for value, total, cnt in Move._read_group(
                    ar_domain, ['recovery_bucket'],
                    ['amount_residual:sum', '__count']):
                if not value:
                    continue
                recovery.append({
                    'key': str(value), 'label': labels.get(value, value),
                    'gross': total or 0.0, 'count': cnt,
                    'status': 'critical' if value == 'previous' else None,
                    'model': 'account.move',
                    'domain': ar_domain + [('recovery_bucket', '=', value)],
                })

        top_debtors = []
        rows = Move._read_group(
            ar_domain, ['partner_id'], ['amount_residual:sum', '__count'])
        rows.sort(key=lambda row: -(row[1] or 0.0))
        for partner, total, cnt in rows[:10]:
            overdue_domain = ar_domain + [
                ('partner_id', '=', partner.id),
                ('invoice_date_due', '<', today_s)]
            overdue = self._sums(
                'account.move', overdue_domain, ['amount_residual:sum'])[0]
            top_debtors.append({
                'key': str(partner.id), 'label': partner.name,
                'gross': total or 0.0, 'count': cnt, 'overdue': overdue,
                'model': 'account.move',
                'domain': ar_domain + [('partner_id', '=', partner.id)],
            })

        services = []
        move_service = self._field('account.move', 'service_line')
        if move_service:
            for value, total, cnt in Move._read_group(
                    ar_domain, [move_service],
                    ['amount_residual:sum', '__count']):
                services.append({
                    'key': str(value or 'none'),
                    'label': value or 'Not linked to a contract',
                    'gross': total or 0.0, 'count': cnt,
                    'model': 'account.move',
                    'domain': ar_domain + [(move_service, '=', value)],
                })
            services.sort(key=lambda item: -item['gross'])
            services = services[:8]

        return {
            'kpis': kpis, 'ageing': ageing, 'recovery': recovery,
            'top_debtors': top_debtors, 'services': services,
            'revenue_months': self._months(
                'account.move',
                lambda s, e: self._invoice_domain() + [
                    ('invoice_date', '>=', fields.Date.to_string(s)),
                    ('invoice_date', '<', fields.Date.to_string(e))],
                ['amount_untaxed_signed:sum', '__count']),
            'collections_months': self._months(
                'account.payment',
                lambda s, e: self._payment_domain(s, e),
                ['amount:sum', '__count']),
            'notes': [],
        }

    # ------------------------------------------------------------------
    # tab 5 — Expenses & Margin
    # ------------------------------------------------------------------

    def _tab_expenses(self, start, end, prev_start, prev_end):
        """Cost structure and what is left after it.

        Where the Finance tab asks whether customers have paid, this one
        asks what the money went on. Expenses are read from the accounts
        they were booked to rather than from vendor bills, so payroll
        journals and depreciation count alongside purchases.
        """
        Line = self.env['account.move.line']
        this_dom = self._expense_line_domain(start, end)
        prev_dom = self._expense_line_domain(prev_start, prev_end)

        spend, spend_count = self._sums(
            'account.move.line', this_dom, ['balance:sum', '__count'])
        prev_spend, _prev_count = self._sums(
            'account.move.line', prev_dom, ['balance:sum', '__count'])

        revenue_domain = self._invoice_domain() + [
            ('invoice_date', '>=', fields.Date.to_string(start)),
            ('invoice_date', '<', fields.Date.to_string(end))]
        revenue, revenue_count = self._sums(
            'account.move', revenue_domain,
            ['amount_untaxed_signed:sum', '__count'])
        profit = revenue - spend

        # Spend by expense account. The chart of accounts is the expense
        # category — §7 of the finance requirements asks for Branch →
        # Department → Category, and the category already lives there. No
        # parallel taxonomy to keep in step.
        by_account = []
        for account, balance, count in Line._read_group(
                this_dom, ['account_id'], ['balance:sum', '__count']):
            if not balance:
                continue
            by_account.append({
                'key': str(account.id),
                'label': account.name or account.code or 'Unnamed account',
                'gross': balance,
                'count': count,
                'model': 'account.move.line',
                'domain': this_dom + [('account_id', '=', account.id)],
            })
        by_account.sort(key=lambda item: -item['gross'])

        # Payroll share is read off the accounts rather than assumed: any
        # account whose name says payroll, wages or salaries.
        payroll = sum(
            row['gross'] for row in by_account
            if any(word in row['label'].casefold()
                   for word in ('payroll', 'wage', 'salar', 'staff cost')))

        kpis = [
            {'label': 'Total expenses', 'gross': spend, 'count': spend_count,
             'model': 'account.move.line', 'domain': this_dom, 'hero': True,
             'delta': self._delta(spend, prev_spend), 'invert': True},
            {'label': 'Invoiced, net of VAT', 'gross': revenue,
             'count': revenue_count, 'model': 'account.move',
             'domain': revenue_domain},
            {'label': 'Net of expenses', 'gross': profit,
             'note': 'invoiced less expenses booked in the same window; '
                     'not a statutory result'},
            {'label': 'Margin', 'pct': self._pct(profit, revenue),
             'note': 'net of expenses against invoiced'},
            {'label': 'Payroll share', 'pct': self._pct(payroll, spend),
             'note': 'accounts named payroll, wages or salaries, '
                     'against total spend'},
        ]

        return {
            'kpis': kpis,
            'by_account': by_account[:12],
            'by_emirate': self._expenses_by_emirate(start, end),
            'expense_months': self._months(
                'account.move.line',
                lambda s, e: self._expense_line_domain(s, e),
                ['balance:sum', '__count']),
            'revenue_months': self._months(
                'account.move',
                lambda s, e: self._invoice_domain() + [
                    ('invoice_date', '>=', fields.Date.to_string(s)),
                    ('invoice_date', '<', fields.Date.to_string(e))],
                ['amount_untaxed_signed:sum', '__count']),
            'notes': [],
        }

    @api.model
    def _expenses_by_emirate(self, start, end):
        """Cost per branch, off the Emirate analytic dimension.

        That dimension is the branch: aabaan_finance_core autofills it on
        every invoice line and enforces it on posting, so the analytic
        items are where a per-emirate cost actually lives. Costs arrive
        there as negative amounts, so they are flipped for display.

        Spend carrying no Emirate tag is not spread across branches on an
        assumption — an allocation rule for shared overheads is a
        management decision, not something a dashboard should invent.
        """
        plan = self._emirate_plan()
        if not plan:
            return []
        domain = [
            ('account_id.root_plan_id', '=', plan.id),
            ('amount', '<', 0),
            ('date', '>=', fields.Date.to_string(start)),
            ('date', '<', fields.Date.to_string(end)),
        ]
        rows = []
        for account, amount, count in self.env['account.analytic.line']._read_group(
                domain, ['account_id'], ['amount:sum', '__count']):
            rows.append({
                'key': str(account.id),
                'label': account.name or 'Unnamed',
                'gross': -(amount or 0.0),
                'count': count,
                'model': 'account.analytic.line',
                'domain': domain + [('account_id', '=', account.id)],
            })
        rows.sort(key=lambda item: -item['gross'])
        return rows

    # ------------------------------------------------------------------
    # tab 6 — Cash & Bank
    # ------------------------------------------------------------------

    def _tab_cash(self, start, end, prev_start, prev_end):
        """Liquidity: what is in the accounts, and what moved through them.

        Deliberately not split by emirate. A bank account belongs to the
        company, not to a branch, and dividing a shared balance between
        branches would be a made-up number.
        """
        Line = self.env['account.move.line']
        journals = self._cash_journals()
        window = self._cash_line_domain(start, end)
        if window is None:
            return {
                'kpis': [], 'accounts': [], 'flow_months': [],
                'transactions': [],
                'notes': ['No bank or cash journal has a default account set, '
                          'so there is no balance to read. Set one under '
                          'Accounting → Configuration → Journals.'],
            }

        inflow, _in_count = self._sums(
            'account.move.line', window + [('debit', '>', 0)],
            ['debit:sum', '__count'])
        outflow, _out_count = self._sums(
            'account.move.line', window + [('credit', '>', 0)],
            ['credit:sum', '__count'])

        # Balance is every posted movement up to the end of the window,
        # not just the window itself — a period's opening balance is part
        # of what is in the bank today.
        to_date = self._cash_line_domain(None, end)
        balance, _bal_count = self._sums(
            'account.move.line', to_date, ['balance:sum', '__count'])

        accounts = []
        for journal in journals:
            account = journal.default_account_id
            if not account:
                continue
            domain = [('account_id', '=', account.id),
                      ('parent_state', '=', 'posted'),
                      ('date', '<', fields.Date.to_string(end))]
            jbal, jcount = self._sums(
                'account.move.line', domain, ['balance:sum', '__count'])
            accounts.append({
                'key': str(journal.id),
                'label': journal.name,
                'gross': jbal,
                'count': jcount,
                'model': 'account.move.line',
                'domain': domain,
            })
        accounts.sort(key=lambda item: -item['gross'])

        kpis = [
            {'label': 'Cash and bank', 'gross': balance,
             'count': len(accounts), 'model': 'account.move.line',
             'domain': to_date, 'hero': True,
             'note': 'balance across %s account%s at the end of the window'
                     % (len(accounts), '' if len(accounts) == 1 else 's')},
            {'label': 'Money in', 'gross': inflow,
             'model': 'account.move.line',
             'domain': window + [('debit', '>', 0)]},
            {'label': 'Money out', 'gross': outflow,
             'model': 'account.move.line',
             'domain': window + [('credit', '>', 0)]},
            {'label': 'Net movement', 'gross': inflow - outflow,
             'note': 'money in less money out over this window'},
        ]

        transactions = []
        for line in Line.search(window, order='date desc, id desc', limit=12):
            transactions.append({
                'key': str(line.id),
                'label': (line.move_id.ref or line.name
                          or line.move_id.name or 'Movement'),
                'account': line.account_id.name,
                'partner': line.partner_id.display_name or '—',
                'date': fields.Date.to_string(line.date),
                'gross': line.debit - line.credit,
                'model': 'account.move',
                'domain': [('id', '=', line.move_id.id)],
            })

        # Built from the account ids directly rather than by calling
        # _cash_line_domain again: that helper returns None when no cash
        # account exists, and `or []` would quietly widen the month series
        # to every line in the ledger. The ids are already known here.
        account_ids = journals.mapped('default_account_id').ids

        def month_domain(m_from, m_to, side):
            return [('account_id', 'in', account_ids),
                    ('parent_state', '=', 'posted'),
                    ('date', '>=', fields.Date.to_string(m_from)),
                    ('date', '<', fields.Date.to_string(m_to)),
                    (side, '>', 0)]

        return {
            'kpis': kpis,
            'accounts': accounts,
            'flow_months': self._months(
                'account.move.line',
                lambda s, e: month_domain(s, e, 'debit'),
                ['debit:sum', '__count']),
            'out_months': self._months(
                'account.move.line',
                lambda s, e: month_domain(s, e, 'credit'),
                ['credit:sum', '__count']),
            'transactions': transactions,
            'notes': [],
        }

    # ------------------------------------------------------------------
    # tab 7 — AMC & Renewals
    # ------------------------------------------------------------------

    def _tab_amc(self, start, end, prev_start, prev_end):
        Sale = self.env['sale.order']
        Task = self.env['project.task']
        book = self._book_domain()
        today = fields.Date.context_today(self)
        today_s = fields.Date.to_string(today)
        now_s = fields.Datetime.to_string(fields.Datetime.now())
        kpis, buckets, timeline, notes = [], [], [], []

        gross, count = self._sums(
            'sale.order', book, ['amount_total:sum', '__count'])
        kpis.append({
            'label': 'Contracts under management', 'gross': gross,
            'count': count, 'model': 'sale.order', 'domain': book,
            'hero': True})

        end_field = self._field('sale.order', 'contract_end')
        if end_field:
            in90 = fields.Date.to_string(today + timedelta(days=90))

            def bucket(key, label, extra, status=None):
                domain = book + extra
                total, cnt = self._sums(
                    'sale.order', domain, ['amount_total:sum', '__count'])
                buckets.append({
                    'key': key, 'label': label, 'gross': total, 'count': cnt,
                    'status': status, 'model': 'sale.order', 'domain': domain})

            bucket('past', 'Past end-of-term',
                   [(end_field, '!=', False), (end_field, '<', today_s)],
                   'critical')
            bucket('next90', 'Renewing within 90 days',
                   [(end_field, '>=', today_s), (end_field, '<=', in90)],
                   'warning')
            bucket('later', 'Beyond 90 days', [(end_field, '>', in90)])
            bucket('open_ended', 'No end date set', [(end_field, '=', False)])

            month_start = today.replace(day=1)
            past_domain = book + [
                (end_field, '!=', False),
                (end_field, '<', fields.Date.to_string(month_start))]
            p_total, p_cnt = self._sums(
                'sale.order', past_domain, ['amount_total:sum', '__count'])
            timeline.append({
                'key': 'past', 'label': 'Overdue', 'gross': p_total,
                'count': p_cnt, 'status': 'critical',
                'model': 'sale.order', 'domain': past_domain})
            for offset in range(12):
                m_from = month_start + relativedelta(months=offset)
                m_to = m_from + relativedelta(months=1)
                m_domain = book + [
                    (end_field, '>=', fields.Date.to_string(m_from)),
                    (end_field, '<', fields.Date.to_string(m_to))]
                m_total, m_cnt = self._sums(
                    'sale.order', m_domain, ['amount_total:sum', '__count'])
                timeline.append({
                    'key': m_from.strftime('%Y-%m'),
                    'label': m_from.strftime('%b'),
                    'gross': m_total, 'count': m_cnt,
                    'model': 'sale.order', 'domain': m_domain})
        else:
            notes.append('Renewal dates need a contract end date on the '
                         'sale order (fm_end_date, or the Subscriptions '
                         'app\'s end_date).')

        # Contracts at risk. The cockpit health score is a computed,
        # non-stored field — it cannot be filtered or grouped in a query,
        # and scoring 600+ contracts one by one would be far too slow for
        # a dashboard. The same underlying evidence is therefore rebuilt
        # here in two batched queries: overdue visits and escalations, per
        # contract. Both are real counts, not a modelled score.
        at_risk = []
        contract_field = self._field('project.task', 'contract')
        if contract_field and 'planned_date_begin' in Task._fields:
            open_fsm = self._fsm_domain() + [('stage_id.fold', '=', False)]
            overdue_by_order = {}
            for order, cnt in Task._read_group(
                    open_fsm + [('planned_date_begin', '<', now_s)],
                    [contract_field], ['__count']):
                if order:
                    overdue_by_order[order.id] = cnt
            escalated_by_order = {}
            if 'sla_escalated' in Task._fields:
                for order, cnt in Task._read_group(
                        open_fsm + [('sla_escalated', '=', True)],
                        [contract_field], ['__count']):
                    if order:
                        escalated_by_order[order.id] = cnt

            order_ids = set(overdue_by_order) | set(escalated_by_order)
            if order_ids:
                orders = Sale.browse(sorted(order_ids)).exists().filtered(
                    lambda o: o.state == 'sale')
                has_end = bool(end_field)
                for order in orders:
                    overdue = overdue_by_order.get(order.id, 0)
                    escalated = escalated_by_order.get(order.id, 0)
                    reasons = []
                    if overdue:
                        reasons.append('%s visit%s past planned date'
                                       % (overdue, '' if overdue == 1 else 's'))
                    if escalated:
                        reasons.append('%s escalated' % escalated)
                    days_left = None
                    if has_end and order[end_field]:
                        days_left = (order[end_field] - today).days
                        if 0 <= days_left <= 90:
                            reasons.append('renews in %s days' % days_left)
                        elif days_left < 0:
                            reasons.append('past end of term')
                    at_risk.append({
                        'key': str(order.id), 'label': order.name,
                        'partner': order.partner_id.name or '',
                        'gross': order.amount_total,
                        'overdue': overdue, 'escalated': escalated,
                        'days_left': days_left,
                        'reason': ' · '.join(reasons),
                        'model': 'sale.order',
                        'domain': [('id', '=', order.id)],
                    })
                at_risk.sort(
                    key=lambda item: (-item['escalated'], -item['overdue'],
                                      -item['gross']))
                at_risk = at_risk[:12]
        else:
            notes.append('Contracts at risk needs Field Service visits linked '
                         'to their contract.')

        # Compliance documents expiring — from the service-contracts pack.
        documents = []
        doc_model, doc_field = self._compliance_source()
        if doc_model:
            Doc = self.env[doc_model]
            soon = fields.Date.to_string(today + timedelta(days=60))
            for key, label, extra, status in (
                    ('expired', 'Expired', [
                        (doc_field, '!=', False),
                        (doc_field, '<', today_s)], 'critical'),
                    ('soon', 'Expiring within 60 days', [
                        (doc_field, '>=', today_s),
                        (doc_field, '<=', soon)], 'warning')):
                cnt = Doc.search_count(extra)
                if cnt:
                    documents.append({
                        'key': key, 'label': label, 'count': cnt,
                        'status': status,
                        'model': doc_model, 'domain': extra})

        if 'cockpit_unscheduled_over' in Sale._fields:
            notes.append(
                'Call-out entitlement overuse is shown per contract on the '
                'Contract Cockpit tab — it is a computed field and cannot be '
                'totalled in a dashboard query.')

        return {
            'kpis': kpis, 'buckets': buckets, 'timeline': timeline,
            'at_risk': at_risk, 'documents': documents,
            'emirates': self._group_amounts(
                'sale.order', book, self._field('sale.order', 'branch')),
            'service_lines': self._group_amounts(
                'sale.order', book, self._field('sale.order', 'service_line')),
            'notes': notes,
        }
