# FM Reports

Reports hub (brief §7.7). Depends on `fm_workorder`, `fm_compliance`, `fm_ppm`.

## Decision log (brief §2.2)
- **OWL client action `fm_reports_hub`** — a card catalog grouped into
  Operational / Financial / Compliance & Audit; each card opens an existing
  action via the action service. Built from the §7.7 spec + `--fm-*` tokens.
- No new models — pure presentation over existing actions.

## Deferred
- Scheduled-report metadata and saved `ir.actions.report` exports (§7.7) — the
  hub currently links to the live list/analysis actions; PDF report templates
  land with the report layer. Exact visual match awaits the `/prototypes/` file.
