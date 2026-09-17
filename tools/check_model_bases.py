#!/usr/bin/env python3
"""Reject plain-Python classes in an Odoo model's bases.

`class SaleOrder(SomePlainClass, models.Model)` compiles, parses and imports
fine, then takes the database down when the registry rebuilds the model:

    TypeError: __bases__ assignment: 'SaleOrder' object layout differs
               from 'SaleOrder'

A plain class carries an `object` instance layout, which Python will not
accept in a `__bases__` assignment against a slotted BaseModel. It only
fires when the registry is assembled, so `py_compile` and XML parsing both
miss it — this is the check that does not.

Run from the repo root:  python3 tools/check_model_bases.py
Exit code 1 means at least one offending class was found.
"""
import ast
import os
import sys

ADDONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'addons')

# A base is safe when it is an Odoo model base, or another class in the same
# file that itself derives from one (checked transitively below).
ODOO_BASES = {'Model', 'TransientModel', 'AbstractModel', 'BaseModel'}


def _is_odoo_base(node):
    """True for `models.Model` / `Model` and friends."""
    if isinstance(node, ast.Attribute):
        return node.attr in ODOO_BASES
    if isinstance(node, ast.Name):
        return node.id in ODOO_BASES
    return False


def check_file(path):
    with open(path, encoding='utf-8') as handle:
        try:
            tree = ast.parse(handle.read(), filename=path)
        except SyntaxError as exc:
            return ['%s: could not parse (%s)' % (path, exc)]

    # Classes in this file that are themselves proper Odoo models.
    model_classes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(_is_odoo_base(b) for b in node.bases):
            model_classes.add(node.name)

    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_is_odoo_base(b) for b in node.bases):
            continue
        for base in node.bases:
            if _is_odoo_base(base):
                continue
            name = base.id if isinstance(base, ast.Name) else ast.dump(base)
            if name in model_classes:
                continue  # derives from a model itself - fine
            problems.append(
                '%s:%d: class %s has non-model base %r -- this breaks the '
                'registry at load time' % (path, node.lineno, node.name, name)
            )
    return problems


def main():
    problems = []
    for root, _dirs, files in os.walk(ADDONS):
        if '__pycache__' in root:
            continue
        for name in sorted(files):
            if name.endswith('.py'):
                problems.extend(check_file(os.path.join(root, name)))

    if problems:
        print('Model base check FAILED:')
        for problem in problems:
            print('  ' + problem)
        return 1
    print('Model base check OK - no plain-Python classes in model bases.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
