# -*- coding: utf-8 -*-
"""Contracts are written in Sales, not in FM.

The first tests in this repository. They exist because the change they
cover is a behavioural guarantee -- "you cannot create an FM contract
here" -- and a guarantee nothing checks is a comment, not a control.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFmContractCreation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Contract Block Test"})

    def _vals(self):
        return {
            "partner_id": self.partner.id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "account_manager_id": self.env.user.id,
        }

    def test_creating_a_contract_is_refused(self):
        """The block is on the model, not the button: import, RPC and a
        stray script all reach create() without ever seeing a view."""
        with self.assertRaises(UserError):
            self.env["fm.contract"].create(self._vals())

    def test_the_refusal_says_where_to_go_instead(self):
        """A block that does not say what to do instead is an obstacle,
        not a control."""
        try:
            self.env["fm.contract"].create(self._vals())
        except UserError as exc:
            message = str(exc)
        else:
            self.fail("creating an FM contract should have been refused")
        self.assertIn("Sales", message)

    def test_the_escape_hatch_is_a_context_key(self):
        """Data migration and tests still need a way through. It is a
        context key rather than a group, because the paths that legitimately
        create contracts are code, not a category of user who would then
        hold that right permanently."""
        contract = self.env["fm.contract"].with_context(
            fm_allow_contract_create=True).create(self._vals())
        self.assertTrue(contract.id)
        self.assertTrue(contract.contract_number)

    def test_existing_contracts_stay_editable(self):
        """Only creation moved. A contract already made must still be
        readable and writable, or the transition breaks live work."""
        contract = self.env["fm.contract"].with_context(
            fm_allow_contract_create=True).create(self._vals())
        contract.write({"state": "active"})
        self.assertEqual(contract.state, "active")
        contract.action_terminate()
        self.assertEqual(contract.state, "terminated")
