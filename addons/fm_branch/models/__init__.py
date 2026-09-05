# -*- coding: utf-8 -*-
# The mixin extension first: models that inherit it are composed in
# import order, so extending it after sale.order would miss it there.
from . import fm_agreement_mixin
from . import fm_branch
from . import sale_order
from . import fm_contract
from . import fm_contract_agreement_template
from . import fm_contract_wizard
from . import project_task
from . import hr_employee
