# -*- coding: utf-8 -*-
"""A technician sees only the jobs assigned to them.

Required feature #10 of the client's process document. Before this, the FM
Field Service project set no privacy and no module added a technician rule,
so every internal user could read every visit in every branch. "My Tasks"
was a filter, which is a convenience, not a restriction.

The rule is global rather than group-scoped, and these tests are mostly
about *that*: Odoo OR-s a user's group rules together, so a technician who
is also a project user would keep project's own permissive rule and see
everything. A test that only checked "the technician sees their own job"
would pass against a rule that restricts nothing.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTechnicianVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)
        cls.technician = cls._make_user("fm_tech", ["fm_branding.group_fm_technician"])
        cls.other_tech = cls._make_user("fm_tech2", ["fm_branding.group_fm_technician"])
        cls.dispatcher = cls._make_user("fm_disp", ["fm_branding.group_fm_dispatcher"])
        cls.mine = cls._make_visit("Mine", cls.technician)
        cls.theirs = cls._make_visit("Theirs", cls.other_tech)

    @classmethod
    def _make_user(cls, login, group_xmlids):
        groups = [cls.env.ref("project.group_project_user").id]
        for xmlid in group_xmlids:
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups.append(group.id)
        return cls.env["res.users"].create({
            "name": login, "login": login, "groups_id": [(6, 0, groups)],
        })

    @classmethod
    def _make_visit(cls, name, user):
        vals = {"name": name, "user_ids": [(6, 0, user.ids)], "fm_wo_type": "reactive"}
        if cls.project:
            vals["project_id"] = cls.project.id
        return cls.env["project.task"].create(vals)

    def _visible(self, user):
        return self.env["project.task"].with_user(user).search([
            ("id", "in", (self.mine + self.theirs).ids)
        ])

    def test_a_technician_sees_their_own_visit(self):
        self.assertIn(self.mine, self._visible(self.technician))

    def test_a_technician_cannot_see_someone_elses_visit(self):
        """The one that matters. A group-scoped rule would be OR-ed with
        project's own and this would still return both."""
        self.assertNotIn(self.theirs, self._visible(self.technician))

    def test_a_technician_cannot_read_someone_elses_visit_directly(self):
        """Not just filtered out of a search — unreadable by id, so the
        mobile app and a guessed URL are covered too."""
        with self.assertRaises(AccessError):
            self.theirs.with_user(self.technician).read(["name"])

    def test_a_dispatcher_still_sees_every_visit(self):
        """Dispatch is the whole job. group_fm_manager, _account_manager and
        _admin all imply dispatcher, so this covers them too."""
        visible = self._visible(self.dispatcher)
        self.assertIn(self.mine, visible)
        self.assertIn(self.theirs, visible)

    def test_a_task_that_is_not_an_fm_visit_is_untouched(self):
        """The rule is about work orders. An ordinary project task carries
        no fm_wo_type and is none of its business."""
        plain = self.env["project.task"].create({
            "name": "Not a visit", "user_ids": [(6, 0, self.other_tech.ids)],
        })
        found = self.env["project.task"].with_user(self.technician).search(
            [("id", "=", plain.id)])
        self.assertEqual(found, plain)
