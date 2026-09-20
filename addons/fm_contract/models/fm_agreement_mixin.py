# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models

# ----------------------------------------------------------------------
# Agreement placeholders
# ----------------------------------------------------------------------
# Wording that is the same for every customer except for a handful of
# facts -- the dates, the visit count, the licence -- is written once with
# a placeholder where each fact goes, and the contract fills them in.
#
# This is the mechanism a set of Studio server actions on the database was
# providing. Theirs rebuilt the stored text on every write, which is why it
# also needed a "Lock terms (stop auto-rebuild)" flag: a rebuild cannot
# tell a fact it should refresh from a sentence somebody typed.
#
# This one never rewrites the wording. The placeholder stays in the stored
# text and is resolved when the text is used, so a fact that changes -- a
# licence number filled in on the branch next week -- is simply right the
# next time the document is produced, and an edit is never at risk.
#
# The names are the client's own, so wording already written against the
# Studio engine keeps working.
AGREEMENT_PLACEHOLDERS = {
    "CLIENT": "the customer's name",
    "SITE": "the site address",
    "CONTACT": "the customer's contact",
    "START": "the contract start date",
    "END": "the contract end date",
    "VISITS": "the number of visits a year",
    "CALLOUTS": "the free call-outs included",
    "WARRANTY": "the warranty period",
    "SLA": "the complaint response promise",
    "LICENCE": "the operating licence number",
}

# Deliberately tolerant of spacing ({{ START }} and {{START}} both work)
# and deliberately NOT tolerant of lowercase: a placeholder has to be
# distinguishable from prose at a glance by whoever is writing the
# wording, and {{start}} in the middle of a sentence is not.
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")

# What stands in for a fact the contract cannot supply. The pencil is the
# Studio layer's own marker, kept so the two produce the same-looking
# document while both exist.
#
# It prints. That is the point: an agreement that is missing the licence
# number says so on the page, where somebody reading it before it goes to
# a customer will see it. Silently printing nothing is how a blank lands
# on a signature page.
UNRESOLVED_MARKER = "\u270e"

# Generic starting wording — pre-filled into every new contract's editable
# Printed Agreement fields (see the field defaults below), so there is always
# visible, editable text in the form from the moment a contract is created,
# not only after a template is picked. These are the same fallbacks
# fm_documents' reports use when a field is left blank, kept in sync manually
# since one lives in Python (as a default) and the other in QWeb (as a
# fallback) — update both together if you change the wording.
DEFAULT_QUOTATION_INTRO_TEXT = (
    "With reference to the above subject and our site inspection, we are "
    "pleased to provide our best quotation for the services described below."
)
DEFAULT_SCOPE_METHOD_TEXT = (
    "Trained operators will inspect the premises prior to any service "
    "activity to assess requirements, then carry out the work using methods "
    "and materials approved by the relevant UAE municipal and environmental "
    "authorities."
)
DEFAULT_EXCLUSIONS_TEXT = "This contract excludes anything not explicitly listed under Article 3."


def _default_service_text(self):
    return (
        "%s agrees to supply the services described below to the Second "
        "Party at the site stated above, in accordance with the schedule "
        "detailed in this agreement. The First Party will ensure that "
        "everyone providing the services has the necessary training and "
        "authorization to do so." % (self.env.company.name or "The First Party")
    )


def _default_schedule_text(self):
    return (
        "The customer agrees to fulfil all technical guidelines requested by "
        "%s to secure the best results. The Second Party will make its "
        "representative available with the technicians during treatment. Any "
        "area not made ready for a scheduled visit will be skipped and "
        "treated on the next scheduled visit." % (self.env.company.name or "the First Party")
    )


class FmAgreementMixin(models.AbstractModel):
    """The printed-agreement wording carried by anything that can be a
    contract — today ``sale.order`` (where contracts are written now) and the
    legacy ``fm.contract`` (frozen, on its way out).

    The wording rules have real behaviour in them, and one of them was a bug
    once (see ``_apply_agreement_template_wording``). Two copies of a rule
    like that drift, and the copy nobody is looking at is the one that goes
    wrong quietly, so both models read this single definition.

    Field names are identical on every model using the mixin. The onchange
    *wiring* is not here: the fields that trigger it (the service line, the
    covered assets) are named per model, so each concrete model declares its
    own small ``@api.onchange`` and calls the helpers below.
    """

    _name = "fm.agreement.mixin"
    _description = "FM Printed Agreement Wording"

    subject = fields.Char(
        string="Contract Subject",
        help="Printed under the contract header, e.g. 'PEST CONTROL TREATMENT "
        "FOR ROYAL APARTMENT G+11'. Defaults to the customer name if blank.",
    )
    scope_notes = fields.Text(
        string="Scope of Work (site wording)",
        help="Free text describing the areas/site covered, printed on the "
        "agreement. Falls back to the Inclusions list if blank.",
    )
    treatment_notes = fields.Text(
        string="Treatment / Method Notes",
        help="Optional — treatment methods, chemicals/equipment used, etc. "
        "Only printed if set.",
    )
    payment_terms_note = fields.Text(
        string="Payment Terms (printed wording)",
        help="e.g. '50% at the time of signing, 50% after 6 months'.",
    )
    unscheduled_visits_included = fields.Integer(
        string="Unscheduled Visits Included",
        default=2,
        help="Number of unscheduled/ad-hoc visits included at no extra charge "
        "over the contract term, stated on the printed agreement.",
    )
    termination_notice_days = fields.Integer(
        string="Termination Notice (days)",
        default=30,
        help="Notice period either party must give to cancel auto-renewal, "
        "stated on the printed agreement.",
    )
    complaint_response_hours = fields.Integer(
        string="Complaint Response Time (hours)",
        default=24,
        help="Hours within which the team commits to visiting a site after a "
        "complaint/infestation report, stated on the printed quotation.",
    )
    agreement_template_id = fields.Many2one(
        "fm.contract.agreement.template",
        string="Agreement Wording Template",
        help="Per-service (and per-branch, if fm_branch is installed) wording "
        "used to seed the editable text below. Selecting a template copies its "
        "wording into this contract's own fields — the shared template itself "
        "is never changed, and you're free to edit your copy.",
    )
    # Per-contract editable copies of the template wording (see
    # _apply_agreement_template_wording). Kept as separate fields — rather than
    # reading the template live in the report — so editing one contract's
    # wording never affects any other contract using the same template.
    quotation_intro_text = fields.Text(
        string="Quotation Intro (editable)",
        default=DEFAULT_QUOTATION_INTRO_TEXT,
        help="Quotation greeting/intro paragraph. Pre-filled with generic "
        "wording; replaced if you pick a template, and always freely editable.",
    )
    scope_method_text = fields.Text(
        string="Scope of Work Methodology (editable)",
        default=DEFAULT_SCOPE_METHOD_TEXT,
        help="Quotation's 'Scope of Work' methodology paragraph. Pre-filled "
        "with generic wording; replaced if you pick a template, and always "
        "freely editable.",
    )
    service_text = fields.Text(
        string="Article 2 — Service (editable)",
        default=_default_service_text,
        help="Service Agreement Article 2 wording. Pre-filled with generic "
        "wording; replaced if you pick a template, and always freely editable.",
    )
    schedule_text = fields.Text(
        string="Article 4 — Service Schedule (editable)",
        default=_default_schedule_text,
        help="Service Agreement Article 4 wording. Pre-filled with generic "
        "wording; replaced if you pick a template, and always freely editable.",
    )
    exclusions_text = fields.Text(
        string="Default Exclusions (editable)",
        default=DEFAULT_EXCLUSIONS_TEXT,
        help="Fallback Article 6 / Quotation exclusions wording, used only "
        "when this contract has no Exclusions listed. Pre-filled with generic "
        "wording; replaced if you pick a template, and always freely editable.",
    )
    agreement_standalone = fields.Boolean(
        string="Template Defines the Full Document",
        help="Copied from the selected template. When on, the printed Service "
        "Agreement renders THIS contract's article list (Additional Terms, "
        "auto-numbered after the Duration article) as the whole document body "
        "— matching each service's real structure — instead of the generic "
        "18-article skeleton.",
    )

    # ``agreement_line_ids`` is deliberately NOT declared here: it is a
    # One2many whose inverse field differs per model, so each concrete model
    # declares its own. Everything below assumes the name exists.

    # ------------------------------------------------------------------
    # Placeholders
    # ------------------------------------------------------------------
    fm_agreement_unresolved_count = fields.Integer(
        string="Unfilled Agreement Facts",
        compute="_compute_fm_agreement_unresolved",
        help="How many placeholders in this contract's wording have "
             "nothing to resolve to. Each one prints as a pencil mark on "
             "the document rather than silently as nothing.",
    )
    fm_agreement_unresolved_names = fields.Char(
        string="Unfilled",
        compute="_compute_fm_agreement_unresolved",
        help="Which facts are missing, in the words of whoever has to go "
             "and find them.",
    )

    def _fm_agreement_placeholder_values(self):
        """{placeholder name: value} for this contract.

        Empty here. Every value depends on a field some concrete model
        declares, and this mixin cannot name them -- so each module
        contributes what it can see by overriding this on ``sale.order``
        (fm_contract the dates and terms, fm_fsm the visit count,
        fm_branch the licence) rather than by extending this mixin.

        That is not a stylistic choice. Extending an AbstractModel only
        reaches the concrete models built *before* the extension is
        registered, so a mixin override added by a later module would
        never run on a sale.order composed in fm_contract -- silently,
        with no error. A plain _inherit on the concrete model always
        runs.

        A name mapped to a falsy value counts as unresolved, which is why
        the contributors can return their fields unguarded.
        """
        self.ensure_one()
        return {}

    def _fm_agreement_texts(self):
        """Every piece of wording a placeholder could be written into."""
        self.ensure_one()
        return [
            self.quotation_intro_text,
            self.scope_method_text,
            self.service_text,
            self.schedule_text,
            self.exclusions_text,
            self.scope_notes,
            self.treatment_notes,
            self.payment_terms_note,
        ]

    def _fm_render_agreement_text(self, text):
        """The wording with its placeholders filled in.

        Never writes. The stored text keeps its placeholders, so the same
        contract re-rendered after somebody fills in the branch licence is
        simply correct, with nothing to rebuild and no edit overwritten.
        """
        if not text:
            return text
        values = self._fm_agreement_placeholder_values()

        def resolve(match):
            name = match.group(1)
            value = values.get(name)
            if value:
                return str(value)
            # An unknown name is shown as written rather than blanked: a
            # typo in the wording should look like a typo, not like a
            # fact nobody filled in.
            description = AGREEMENT_PLACEHOLDERS.get(name)
            if description is None:
                return match.group(0)
            return "%s %s" % (UNRESOLVED_MARKER, description)

        return PLACEHOLDER_RE.sub(resolve, text)

    def _fm_agreement_unresolved(self):
        """The placeholder names this contract's wording uses and cannot
        fill, in the order they are defined rather than the order they
        happen to appear."""
        self.ensure_one()
        values = self._fm_agreement_placeholder_values()
        used = set()
        for text in self._fm_agreement_texts():
            if text:
                used.update(PLACEHOLDER_RE.findall(text))
        return [
            name for name in AGREEMENT_PLACEHOLDERS
            if name in used and not values.get(name)
        ]

    @api.depends(
        "quotation_intro_text", "scope_method_text", "service_text",
        "schedule_text", "exclusions_text", "scope_notes",
        "treatment_notes", "payment_terms_note",
    )
    def _compute_fm_agreement_unresolved(self):
        """Not stored, so it cannot be filtered on -- and should not be.

        Whether a fact is missing depends on fields spread across three
        modules; storing it would mean naming every one of them in a
        depends from a mixin that cannot see them, and a stored value that
        silently stops updating is worse than one computed on sight.
        """
        for record in self:
            missing = record._fm_agreement_unresolved()
            record.fm_agreement_unresolved_count = len(missing)
            record.fm_agreement_unresolved_names = ", ".join(
                AGREEMENT_PLACEHOLDERS[name] for name in missing
            ) or False

    def _find_agreement_template(self, service_line):
        """Hook for fm_branch to also match on branch/state; base
        implementation matches on service line only."""
        return self.env["fm.contract.agreement.template"].search(
            [("service_line", "=", service_line)], limit=1
        )

    def _apply_agreement_template_wording(self):
        """Copy the selected template's wording into this record's own
        editable fields. Deliberately replaces any prior manual edits —
        selecting a (different) template is a deliberate "start from this"
        action, not a passive default.

        Every field is always set to either the template's own value or the
        standard generic default — NEVER left at whatever was there before.
        (An earlier version fell back to "self.field" — the previous value —
        when a field wasn't defined on the new template, which meant
        switching from e.g. "Pest Control — Dubai" (schedule_text set) to
        "Anti-Termite — Standard" (schedule_text blank) left the Dubai
        wording stuck under an Anti-Termite contract. Clearing the template
        entirely uses the same generic defaults, for the same reason.)"""
        t = self.agreement_template_id
        self.quotation_intro_text = (t and t.quotation_intro_text) or DEFAULT_QUOTATION_INTRO_TEXT
        self.scope_method_text = (t and t.scope_method_text) or DEFAULT_SCOPE_METHOD_TEXT
        self.service_text = (t and t.service_text) or _default_service_text(self)
        self.schedule_text = (t and t.schedule_text) or _default_schedule_text(self)
        self.exclusions_text = (t and t.exclusions_default_text) or DEFAULT_EXCLUSIONS_TEXT
        new_lines = [
            (0, 0, {"sequence": line.sequence, "name": line.name, "body": line.body})
            for line in t.line_ids
        ] if t else []
        self.agreement_line_ids = [(5, 0, 0)] + new_lines
        # A template with lines that "defines the full document" makes those
        # lines the printed agreement's article list; without a template (or
        # with a slot-filling template) the generic skeleton prints instead.
        self.agreement_standalone = bool(t and t.replaces_standard_articles and t.line_ids)

    def _fm_apply_template_for_service(self, service_line):
        """Find the template for ``service_line`` and apply its wording.

        Used by the "service was picked" onchange on each concrete model.
        Re-applies even when wording was edited: picking a different service
        is a deliberate "start from this service's wording" action.
        """
        if not service_line:
            return False
        template = self._find_agreement_template(service_line)
        if not template or template == self.agreement_template_id:
            return False
        self.agreement_template_id = template.id
        self._apply_agreement_template_wording()
        return True

    @api.model
    def _fm_infer_service_from_assets(self, assets):
        """The one service line all these assets share, or False.

        Assets spanning two services say nothing useful about which wording
        the contract should start from, so they are left alone rather than
        guessed at.
        """
        lines = {line for line in assets.mapped("service_line") if line}
        return next(iter(lines)) if len(lines) == 1 else False
