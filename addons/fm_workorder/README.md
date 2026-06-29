# FM Work Order

The heart of the platform (brief §5.3, §6.1). Depends on `fm_contract`.

## Decision log (brief §2.2)

| Model | Decision | Rationale |
|---|---|---|
| `fm.workorder` | **Compose with `maintenance.request`** (`_name`+`_inherit`) | Reuse the standard maintenance request while exposing a distinct, FM-specific WO model used across dispatch/PPM/compliance/mobile. |
| Stage machine | **Custom `stage` Selection + `action_stage_change`** | The FM lifecycle (10 stages, pause branches, gated transitions) has no standard equivalent. A single guarded method enforces §6.1 server-side. |
| Checklist / parts / labor | **New line models** | FM execution detail with progress + cost rollups. |
| `fm.checklist.template` | **New model, defined here** | Consumed directly by the WO; `fm_ppm` reuses it (defined here rather than in fm_ppm to avoid a forward dependency). |
| `fm.contract` (extend) | **`_inherit` to add `workorder_ids`** | Resolves the contract↔WO circular reference — the One2many lives in the module that defines the WO. |

## State machine (brief §6.1)

`STAGE_TRANSITIONS` declares the allowed moves. `action_stage_change(new_stage, **kwargs)`:
- rejects illegal transitions,
- stamps `acknowledged_at` / `actual_start` / `actual_end` / `signed_off_at` / cancellation metadata,
- pauses/resumes SLA on `awaiting_*` (accumulating `sla_pause_minutes_total`),
- **gates** `completed` on all mandatory checklist items, and `signed_off` on signature + CSAT,
- posts to the chatter.

## Deferred to later modules

- **SLA actuals / breach / status** and the **contract health algorithm** → `fm_sla` (§6.2, §6.5).
- **Auto-dispatch scoring** (§6.3) and the **dispatch scheduler OWL** → `fm_dispatch` (§7.2).
- **WO → invoice automation** (§6.4) → wired with `fm_sla`/billing.
- **`portal.mixin`** + customer sign-off via portal → `fm_customer_portal`.
- **Stock consumption** (`stock_move_id` on parts) → wired when `stock` is added to the deployment.
- The **OWL work-order form / kanban** (§7.3, §7.4) → once the `/prototypes/` files are provided. Standard form/list/kanban/search ship here.

## Security

Technicians see only their own WOs; dispatchers/managers see all; global multi-company rule (brief §8.2).
