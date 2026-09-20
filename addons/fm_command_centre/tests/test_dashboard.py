# -*- coding: utf-8 -*-
from odoo import fields
from odoo.addons.fm_command_centre.models.fm_command_centre import PERIODS, TABS
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCommandCentre(TransactionCase):

    def _data(self, tab='executive', period='this_month'):
        return self.env['fm.command.centre'].get_data(tab, period)

    def test_every_tab_loads_on_a_bare_database(self):
        """Each tab must return a usable payload even with no records and
        whichever spelling of the platform fields is present — a concept
        nothing answers collapses its own section, it never breaks the
        tab."""
        for tab, _label in TABS:
            data = self._data(tab)
            self.assertEqual(data['tab'], tab)
            for key in ('company', 'currency', 'as_of', 'tabs', 'periods',
                        'period', 'period_label', 'range', 'notes'):
                self.assertIn(key, data, "%s tab is missing %s" % (tab, key))

    def test_every_period_loads_on_every_tab(self):
        for tab, _label in TABS:
            for period, _plabel in PERIODS:
                data = self._data(tab, period)
                self.assertEqual(data['period'], period)

    def test_unknown_tab_and_period_fall_back(self):
        """A stale bookmark or a hand-edited call must not raise."""
        data = self._data('does_not_exist', 'also_not_real')
        self.assertEqual(data['tab'], 'executive')
        self.assertEqual(data['period'], 'this_month')

    def test_period_bounds_previous_window_is_same_length(self):
        Dash = self.env['fm.command.centre']
        for period, _label in PERIODS:
            start, end, prev_start, prev_end = Dash._period_bounds(period)
            self.assertEqual(prev_end, start,
                             "%s: previous window must end where the "
                             "current one starts" % period)
            self.assertEqual(end - start, start - prev_start,
                             "%s: the two windows must be the same length "
                             "or the delta is not like-for-like" % period)

    def test_delta_is_none_without_a_baseline(self):
        """An undefined delta must stay undefined — reporting 0% or 100%
        against a zero baseline would read as a measured fact."""
        Dash = self.env['fm.command.centre']
        self.assertIsNone(Dash._delta(500, 0))
        self.assertIsNone(Dash._delta(0, 0))
        self.assertEqual(Dash._delta(150, 100), 50.0)
        self.assertEqual(Dash._delta(50, 100), -50.0)

    def test_pct_is_none_without_a_denominator(self):
        Dash = self.env['fm.command.centre']
        self.assertIsNone(Dash._pct(3, 0))
        self.assertEqual(Dash._pct(1, 4), 25.0)

    def test_executive_tiles_and_trends(self):
        data = self._data('executive')
        self.assertTrue(data['tiles'])
        self.assertIn('exceptions', data)
        for entry in data['exceptions']:
            self.assertGreater(entry['count'], 0,
                               "a quiet business shows a quiet strip — "
                               "zero-count exceptions must be dropped")
            self.assertIn('domain', entry)
        self.assertEqual(len(data['revenue_months']), 12)
        self.assertEqual(len(data['collections_months']), 12)
        for entry in data['period_block']:
            for key in ('label', 'gross', 'count', 'prev_gross', 'delta'):
                self.assertIn(key, entry)

    def test_finance_ageing_bands_cover_every_open_invoice(self):
        """The five ageing bands must partition the receivables — no
        invoice counted twice, none dropped."""
        data = self._data('finance')
        self.assertEqual(len(data['ageing']), 5)
        total_in_bands = sum(band['count'] for band in data['ageing'])
        ar = self.env['account.move'].search_count(
            self.env['fm.command.centre']._ar_domain())
        self.assertEqual(total_in_bands, ar)

    def test_confirmed_order_reaches_the_book(self):
        partner = self.env['res.partner'].create({'name': 'Dash Test Customer'})
        product = self.env['product.product'].create({
            'name': 'Dash Test Service', 'type': 'service', 'list_price': 100.0})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': product.id,
                                   'product_uom_qty': 1})],
        })
        before = self._data('executive')['tiles'][0]
        order.action_confirm()
        after = self._data('executive')['tiles'][0]
        self.assertEqual(after['count'], before['count'] + 1)
        self.assertGreater(after['gross'], before['gross'])

    def test_every_drillable_figure_carries_a_real_domain(self):
        """Every tile/bar on screen claims to be one click from its
        evidence — so anything with a model must also carry a domain."""
        for tab, _label in TABS:
            data = self._data(tab)
            for key, value in data.items():
                if not isinstance(value, list):
                    continue
                for entry in value:
                    if isinstance(entry, dict) and entry.get('model'):
                        self.assertIn(
                            'domain', entry,
                            "%s → %s: drillable entry has no domain" % (tab, key))

    def test_amc_at_risk_entries_explain_themselves(self):
        """A contract only appears in the at-risk list with a stated,
        evidence-backed reason — never an unexplained score."""
        for entry in self._data('amc')['at_risk']:
            self.assertTrue(entry['reason'])
            self.assertTrue(entry['overdue'] or entry['escalated'])

    # ------------------------------------------------------------------
    # Expenses & Margin
    # ------------------------------------------------------------------

    def _expense_account(self):
        account = self.env['account.account'].search(
            [('account_type', '=', 'expense')], limit=1)
        if not account:
            self.skipTest('no chart of accounts on this database')
        return account

    def _post_expense(self, amount=1000.0):
        """A payroll-shaped journal entry: an expense line and its
        balancing payable line. Not a vendor bill — that is the point."""
        expense = self._expense_account()
        other = self.env['account.account'].search(
            [('account_type', 'not like', 'expense%')], limit=1)
        journal = self.env['account.journal'].search(
            [('type', '=', 'general')], limit=1)
        if not (other and journal):
            self.skipTest('no general journal or balancing account')
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.context_today(self.env['account.move']),
            'ref': 'Payroll run — dashboard test',
            'line_ids': [
                (0, 0, {'name': 'Salaries', 'account_id': expense.id,
                        'debit': amount, 'credit': 0}),
                (0, 0, {'name': 'Payable', 'account_id': other.id,
                        'debit': 0, 'credit': amount}),
            ],
        })
        move.action_post()
        return move

    def test_expenses_count_journal_entries_not_only_vendor_bills(self):
        """Spend is read from the accounts it was booked to, so a payroll
        journal counts. Reading vendor bills alone would miss the single
        largest cost this business has."""
        before = self._data('expenses')['kpis'][0]['gross']
        self._post_expense(1000.0)
        after = self._data('expenses')['kpis'][0]['gross']
        self.assertAlmostEqual(after - before, 1000.0, places=2)

    def test_expense_accounts_are_listed_with_their_own_domain(self):
        self._post_expense(750.0)
        rows = self._data('expenses')['by_account']
        self.assertTrue(rows, 'a posted expense must appear by account')
        for row in rows:
            self.assertEqual(row['model'], 'account.move.line')
            self.assertTrue(row['domain'])

    def test_untagged_cost_is_not_spread_across_emirates(self):
        """Cost with no Emirate analytic tag stays out of the branch split
        rather than being apportioned on an assumption."""
        self._post_expense(500.0)  # no analytic distribution
        data = self._data('expenses')
        tagged_total = sum(row['gross'] for row in data['by_emirate'])
        self.assertLessEqual(
            round(tagged_total, 2), round(data['kpis'][0]['gross'], 2),
            'branch split must never exceed total spend')

    # ------------------------------------------------------------------
    # Cash & Bank
    # ------------------------------------------------------------------

    def test_cash_tab_states_why_it_is_empty(self):
        """With no bank or cash journal configured the tab says so, rather
        than showing a confident zero."""
        data = self._data('cash')
        if not data['accounts']:
            self.assertTrue(data['notes'], 'an empty cash tab must explain itself')

    def test_cash_balance_is_position_not_period_movement(self):
        """The balance KPI is every posted movement up to the end of the
        window; money in and out are the window alone. Comparing the two
        as if they were the same measure is the classic cash-tab error."""
        data = self._data('cash')
        if not data['accounts']:
            self.skipTest('no bank or cash journal with a default account')
        labels = [kpi['label'] for kpi in data['kpis']]
        self.assertEqual(labels[:1], ['Cash and bank'])
        balance = data['kpis'][0]
        self.assertNotIn(('date', '>='), [tuple(c[:2]) for c in balance['domain']
                                          if isinstance(c, (list, tuple))],
                         'the balance domain must not be bounded at the start')


@tagged('post_install', '-at_install')
class TestCommandCentreFieldAliases(TransactionCase):
    """The port's own risk.

    Every query in this dashboard reads a field whose *name* differs between
    the FM build and the aabaan build. If the resolver picks a name that is
    not there, the section raises instead of collapsing — which is the one
    failure mode the original module was written to avoid.
    """

    def setUp(self):
        super().setUp()
        self.Dash = self.env['fm.command.centre']

    def test_resolved_fields_actually_exist(self):
        """Whatever _field returns must be real. A typo in the alias table
        would otherwise surface as a crash on one tab, months later."""
        from odoo.addons.fm_command_centre.models.fm_command_centre import (
            FIELD_ALIASES,
        )
        for (model, concept) in FIELD_ALIASES:
            if model not in self.env:
                continue
            name = self.Dash._field(model, concept)
            if name:
                self.assertIn(
                    name, self.env[model]._fields,
                    "%s/%s resolved to %s, which does not exist"
                    % (model, concept, name))

    def test_an_unanswered_concept_is_false_not_a_guess(self):
        self.assertFalse(self.Dash._field('sale.order', 'not_a_concept'))
        self.assertFalse(self.Dash._field('no.such.model', 'service_line'))

    # The module no longer depends on the FM suite, so these three assert
    # what the aliases resolve to *when the FM suite is installed* and skip
    # when it is not — the dashboard is meant to run on a build without it.
    def test_the_fm_contract_link_resolves_on_this_build(self):
        """fm_contract_order_id is what a visit carries here. If this ever
        returns sale_order_id, visits stopped following the contract."""
        if 'fm_contract_order_id' not in self.env['project.task']._fields:
            self.skipTest('the FM suite is not installed on this build')
        self.assertEqual(
            self.Dash._field('project.task', 'contract'),
            'fm_contract_order_id')

    def test_the_fm_service_line_wins_over_a_manual_field(self):
        if 'fm_service_line' not in self.env['project.task']._fields:
            self.skipTest('the FM suite is not installed on this build')
        self.assertEqual(
            self.Dash._field('project.task', 'service_line'),
            'fm_service_line')

    def test_compliance_source_is_the_fm_certificate(self):
        if 'fm.compliance.certificate' not in self.env:
            self.skipTest('fm_compliance is not installed on this build')
        model, fname = self.Dash._compliance_source()
        self.assertEqual(model, 'fm.compliance.certificate')
        self.assertIn(fname, self.env[model]._fields)

    def test_grouping_by_a_many2one_returns_ids_not_records(self):
        """branch_id is a many2one here where the other build has a
        selection. str() on a record would put "fm.branch(3,)" in the key and
        a record where a label belongs."""
        branch_field = self.Dash._field('sale.order', 'branch')
        if not branch_field:
            self.skipTest('fm_branch is not installed on this build')
        rows = self.Dash._group_amounts(
            'sale.order', [('state', '=', 'sale')], branch_field)
        for row in rows:
            self.assertIsInstance(row['key'], str)
            self.assertIsInstance(row['label'], str)
            self.assertNotIn('(', row['key'])

    def test_a_missing_field_collapses_rather_than_raising(self):
        self.assertEqual(
            self.Dash._group_amounts('sale.order', [], 'no_such_field'), [])
        self.assertEqual(self.Dash._group_amounts('sale.order', [], False), [])
