#!/usr/bin/env python3
"""Every file a module promises to load must exist.

Two ways to break the build by deleting a file, both of which pass
``py_compile`` and an XML parse and only fail when Odoo starts:

1. A path left in a manifest's ``data`` list after the file is gone. Odoo
   raises ``FileNotFoundError`` loading the module and the registry never
   finishes -- on Odoo.sh that is a red production build.
2. A ``from . import x`` left in a package's ``__init__.py`` after
   ``x.py`` is gone. Same outcome, one import earlier.

Both bite hardest in exactly the change that is least interesting to
review: retiring a model and pulling its files out of four modules at
once. Nothing else in this repo looks at these two lists, so this does.

Also reports XML under a module that no manifest loads. That is a
warning, not a failure -- a file can legitimately sit unloaded -- but a
view nobody loads is usually a view somebody meant to delete.

Run from the repo root:  python3 tools/check_manifest_data.py
"""
import ast
import os
import sys

ADDONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "addons")
LOADABLE_DIRS = ("views", "data", "reports", "report", "security", "wizard")


def manifest_data(module_dir):
    path = os.path.join(module_dir, "__manifest__.py")
    with open(path, encoding="utf-8") as fh:
        manifest = ast.literal_eval(fh.read())
    return manifest.get("data", []) + manifest.get("demo", [])


def init_imports(init_path):
    """The module names a package's __init__.py imports from itself."""
    with open(init_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=init_path)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            names.extend(alias.name for alias in node.names)
    return names


def main():
    errors = []
    warnings = []
    checked_data = checked_imports = 0

    for module in sorted(os.listdir(ADDONS)):
        module_dir = os.path.join(ADDONS, module)
        if not os.path.isfile(os.path.join(module_dir, "__manifest__.py")):
            continue

        declared = manifest_data(module_dir)
        for rel in declared:
            checked_data += 1
            if not os.path.isfile(os.path.join(module_dir, rel)):
                errors.append("%s: manifest loads %r, which does not exist" % (module, rel))

        for root, dirs, files in os.walk(module_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            if "__init__.py" not in files:
                continue
            init_path = os.path.join(root, "__init__.py")
            for name in init_imports(init_path):
                checked_imports += 1
                target_py = os.path.join(root, name + ".py")
                target_pkg = os.path.join(root, name, "__init__.py")
                if not (os.path.isfile(target_py) or os.path.isfile(target_pkg)):
                    errors.append("%s: %s imports %r, which does not exist" % (
                        module, os.path.relpath(init_path, module_dir), name))

        loaded = set(declared)
        for sub in LOADABLE_DIRS:
            sub_dir = os.path.join(module_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            for name in sorted(os.listdir(sub_dir)):
                if not name.endswith((".xml", ".csv")):
                    continue
                rel = "%s/%s" % (sub, name)
                if rel not in loaded:
                    warnings.append("%s: %s is not in the manifest -- dead file?" % (module, rel))

    for warning in warnings:
        print("warning: %s" % warning)
    if errors:
        for error in errors:
            print("ERROR: %s" % error)
        print("\n%d problem(s). Odoo would fail to load these modules." % len(errors))
        return 1
    print("Manifest/import check OK - %d data file(s) and %d import(s) resolve."
          % (checked_data, checked_imports))
    return 0


if __name__ == "__main__":
    sys.exit(main())
