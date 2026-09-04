from . import hooks

# Odoo resolves post_init_hook with getattr() on the package, so the name has
# to be bound here — importing the submodule alone leaves it undefined and the
# install aborts. (Same trap as fm_aabaan_setup, PR #88.)
from .hooks import _post_init_website
