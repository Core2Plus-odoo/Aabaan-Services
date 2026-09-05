# -*- coding: utf-8 -*-
# The mixin first: models that inherit an abstract model are composed in
# import order, so defining it after them would miss it silently.
from . import fm_visit_schedule_mixin
from . import project_task
from . import fm_contract
from . import sale_order
