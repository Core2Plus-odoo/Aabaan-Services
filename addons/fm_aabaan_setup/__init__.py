# -*- coding: utf-8 -*-
# The hook name must be bound at package level: Odoo resolves post_init_hook
# with getattr() on odoo.addons.fm_aabaan_setup, so importing the submodule
# alone leaves the attribute undefined and the install aborts.
from .hooks import _post_init_apply
