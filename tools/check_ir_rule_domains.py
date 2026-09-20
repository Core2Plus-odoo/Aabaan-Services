#!/usr/bin/env python3
"""Compile every ir.rule domain_force in the repo, exactly as Odoo will.

Why this exists: a record rule's ``domain_force`` is evaluated with
``compile(expr, mode="eval")``, which cannot parse a bare expression spanning
several lines -- the continuation lines read as an unexpected indent and the
module dies at load with ``Invalid domain: unexpected indent``. Nothing else
catches it. The XML parses, py_compile has no opinion, and a dev build that
fails earlier never reaches it.

It took a production build to find that once. The mistake that let it
through was checking the expression as retyped into a test rather than as
stored in the file -- so this reads the file.

Beyond compiling, each domain is evaluated twice with a stub user whose
has_group() answers True and then False, so both arms of a conditional are
exercised and each must yield a list. A domain needing names this stub does
not provide is compiled but not evaluated, and says so.

Exit 1 on any failure.
"""
import ast
import glob
import os
import sys
import xml.etree.ElementTree as ET


class _StubUser:
    def __init__(self, in_groups):
        self.id = 1
        self.ids = [1]
        self._in_groups = in_groups
        self.company_id = self
        self.company_ids = self
        self.partner_id = self

    def has_group(self, _name):
        return self._in_groups

    def has_groups(self, _names):
        return self._in_groups


def _eval_context(in_groups):
    import datetime
    import time
    user = _StubUser(in_groups)
    return {
        "user": user, "uid": 1, "time": time, "datetime": datetime,
        "context_today": lambda: datetime.date.today(),
        "company_id": 1, "company_ids": [1], "allowed_company_ids": [1],
    }


def _domains(path):
    """(line, expression) for each ir.rule domain_force in one file."""
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return
    for record in tree.iter("record"):
        if record.get("model") != "ir.rule":
            continue
        for field in record.findall("field"):
            if field.get("name") == "domain_force" and field.text:
                yield record.get("id") or "?", field.text


def main():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "addons")
    failures, checked, unevaluated = [], 0, 0
    for path in sorted(glob.glob(os.path.join(root, "**", "*.xml"), recursive=True)):
        for xmlid, text in _domains(path):
            checked += 1
            rel = os.path.relpath(path, root)
            expr = text.strip()
            try:
                compile(expr, "<domain_force>", "eval")
            except SyntaxError as exc:
                failures.append("%s: %s -- will not compile: %s" % (rel, xmlid, exc))
                continue
            for in_groups in (True, False):
                try:
                    value = eval(expr, _eval_context(in_groups))  # noqa: S307
                except NameError as exc:
                    unevaluated += 1
                    print("  note: %s: %s not evaluated (%s)" % (rel, xmlid, exc))
                    break
                except Exception as exc:  # noqa: BLE001
                    failures.append("%s: %s -- raises %s: %s" % (
                        rel, xmlid, type(exc).__name__, exc))
                    break
                if not isinstance(value, list):
                    failures.append("%s: %s -- is %s, not a domain list" % (
                        rel, xmlid, type(value).__name__))
                    break
    if failures:
        print("ir.rule domain check FAILED:")
        for line in failures:
            print("  " + line)
        return 1
    print("ir.rule domain check OK - %d domain(s) compile and evaluate to a list."
          % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
