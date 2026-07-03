# Aabaan FM — Lifecycle Workflow (standard-first)

The end-to-end FM journey, delivered on **native Odoo** with only a thin `fm_*`
layer for the facility-specific fields. Nothing here needs a custom engine — each
stage is a standard app you configure in the UI.

```
 Onboarding ─▶ Contract ─▶ Services ─▶ Scheduling ─▶ Delivery ─▶ Renewal ─▶ Billing ─▶ Health
 (Customer)   (fm.contract) (products)  (FSM visits)  (worksheets) (Subscr.)  (Invoicing) (dashboards)
```

The **Facility Management** app menu is now ordered to match this journey:
**Contracts (Customers first) → Assets → Scheduling & Work Orders → Compliance →
Dashboards → Configuration.**

> Legend: **[UI]** done by clicking in Odoo · **[STUDIO]** needs Studio (Enterprise)
> · **[BUILT]** already coded in the FM suite.

---

## 1. Client onboarding  **[UI]**

Two standard paths — pick per deal size:

- **Quick:** FM → Contracts → **Customers → New**. Capture company, **TRN** in
  *Tax ID*, address, contacts, **branch** (`fm_branch`). This is a native
  `res.partner`.
- **Full sales cycle:** **CRM** lead → **Sales** quotation → confirm. Use when
  you want a pipeline, proposal PDF and won/lost reporting before the contract.

No custom onboarding screen — the native customer form + CRM *is* onboarding.

## 2. Contract  **[BUILT]**

FM → Contracts → **Contracts → New** (`fm.contract`, delegates to `sale.order`):

- Customer, **contract type** (AMC comprehensive / non-comprehensive / break-fix
  / project), **account manager**, start/end, **ACV**, billing frequency.
- **Scope tab:** covered **assets**, service inclusions/exclusions.
- **SLA & penalties:** response/resolution targets (`fm.sla.rule`), penalty
  clauses.
- Products/pricing live on the underlying sales order — **Edit Products (Sales
  Order)** button.

## 3. Services  **[UI/BUILT]**

- Service **products** (Sales → Products) — the billable lines on the contract.
- **Service items** catalog (FM → Contracts → Service Items) for
  inclusions/exclusions wording on the contract PDF.
- **Materials per service** (FM → Configuration → *Service Materials* / **Material
  Forecast**) so consumption can be anticipated (`fm_service_materials`).

## 4. Scheduling  **[BUILT]**

- On the contract **Scheduling** tab set **frequency** + **skip weekends** +
  preferred technician, then **Activate** (or **Generate Visits**). Visits are
  created as native **Field Service tasks** in the *Facility Management* project
  and kept rolling by the daily cron.
- See them on **FM → Scheduling & Work Orders → Visit Calendar** and the
  **Maintenance Calendar** dashboard.

## 5. Delivery — checklists via native **FSM Worksheets**  **[STUDIO]**

Odoo Field Service's **Worksheet** is the standard on-site checklist: the
technician fills it on mobile and it prints on the job report. Set it up once:

1. **Enable worksheets** — Field Service → Configuration → **Settings** → tick
   *Worksheets*. On the **Facility Management** project (Project → Settings),
   enable **Worksheets**.
2. **Build a template** — Field Service → Configuration → **Worksheet Templates
   → New**. Name it (e.g. *Monthly AC PPM*) then **Design Template** to add
   fields in Studio:
   - **Checkboxes** for each check ("Filters cleaned", "Gas pressure OK",
     "Drain flushed", "Thermostat tested").
   - **Float / integer** readings (temperatures, pressures), **selection** for
     pass/fail, **text** for remarks, a **signature** and **photo** field.
   - Mark critical checks **required** so the job can't be validated until ticked.
3. **Assign** the template to the project (or per task). The technician opens the
   task on mobile → **Worksheet** → fills → **Validate** → it appears on the
   printed **Worksheet/Job report**.

Suggested starter templates to build: **AC PPM**, **Water-Tank Cleaning**,
**Pest Control Treatment**, **Fire-System Inspection**, **General Reactive
Callout**. (These map to the service lines in `fm_asset`.)

> Why Studio and not seeded data: each worksheet is a generated model, so it is
> defined in the UI, not XML. This is the standard Odoo mechanism — no custom
> checklist tables to maintain.

## 6. Documents  **[UI]**

- **Per record:** every contract, work order and asset has a **chatter** — drag
  files in (signed contract, permits, certificates, before/after photos). Native.
- **Central library:** the **Documents** app — create workspaces (*Contracts*,
  *Compliance Certificates*, *Permits*) with folders per customer; route incoming
  files with rules.
- **Generated PDFs:** the FM suite already prints **Work Order job sheet**,
  **Contract** and **Compliance Certificate** (bilingual EN/AR, TRN, QR) via
  `fm_documents`.

## 7. Compliance  **[BUILT]**

FM → Compliance → **Regimes** (UAE cadences) and **Certificates**. The watchdog
cron flags expiries and can spin up a remediation **work order** (`project.task`).

## 8. Renewals  **[UI]**

- Contract lifecycle state → **In Renewal Discussion**; `days_to_renewal` and the
  CEO dashboard surface what's expiring.
- Where billing runs on **Subscriptions** (`fm_subscription`), use native
  subscription **renew / upsell** — recurring invoices continue automatically and
  renewal quotations are standard.

## 9. Billing  **[UI/BUILT]**

- Native **Invoicing**: FTA **Tax Invoice** (supplier + TRN, sequential number,
  5% VAT, AED). Invoice from the sales order / subscription.
- Recurring AMC billing via **Subscriptions** at the contract's billing
  frequency; post to the salary/sales journals; collect per your payment terms.

## 10. Health  **[BUILT]**

- **CEO dashboard** — ACV/TCV, revenue YTD, contract health bands, ops severity,
  compliance, by-branch.
- **Maintenance Calendar** — supervisor month view of visits by status.
- **Operations / Contracts** native graph & pivot dashboards.
- Native **Subscription** MRR / churn / health for recurring revenue.

---

### What is code vs. what is clicks

| Stage | Delivered as |
|---|---|
| Contract, scheduling, materials, compliance, dashboards, PDFs | **code** (thin `fm_*` on native) |
| Menu journey order | **code** (menu re-sequence in `fm_fsm`) |
| Onboarding, worksheets/checklists, documents, renewals, billing | **standard Odoo config** (this runbook) |

The rule: if native Odoo already does it, we **configure** it — we don't rebuild it.
