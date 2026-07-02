# UAE Facility Management — Domain Knowledge

Reference for building and configuring the Aabaan FM platform for the UAE
market. Applied throughout the `fm_*` modules (especially `fm_aabaan_config`,
`fm_compliance`, `fm_documents`).

> This is working domain guidance for software configuration, not legal advice.
> Statutory requirements change — confirm current rules with the relevant
> authority before relying on compliance cadences.

---

## 1. Aabaan Services — profile

- UAE facilities-services provider. Core service lines: **pest control, water
  tank cleaning & disinfection, building/facility cleaning, AC/HVAC
  maintenance, plumbing & sanitary**.
- Operating branches modelled as `fm.branch` (emirate offices): **Dubai,
  Sharjah, Ajman, Abu Dhabi** (extendable to the other emirates).
- Work is delivered under **AMC (Annual Maintenance Contracts)** with scheduled
  recurring visits, plus **reactive / break-fix** jobs.

## 2. Commercial & tax (VAT / FTA)

- **Currency: AED.**
- **VAT: standard rate 5%** (some supplies zero-rated/exempt). Configure a 5%
  sale tax; most FM services are standard-rated.
- **TRN** (Tax Registration Number) is the company's `vat` field. It **must**
  appear on tax invoices — surfaced on the FM PDF layouts (`fm_documents`).
- A standard Odoo customer invoice (`account.move`) is an **FTA-compliant Tax
  Invoice** when it carries: supplier name + TRN, invoice date & sequential
  number, customer details, line description, taxable amount, VAT rate &
  amount, and total. Keep AED as presentation currency.
- **Subscriptions** (`sale.subscription`) drive recurring AMC billing; Odoo
  raises the periodic tax invoice automatically.

## 3. Regulatory compliance (modelled in `fm_compliance`)

Compliance is modelled as **regimes** (`fm.compliance.regime`) with **task
templates** (renewal cadence + certificate flag), producing **certificates**
(`fm.compliance.certificate`) tracked by a watchdog cron. UAE-relevant regimes:

| Regime | Authority | Typical cadence | Notes |
|---|---|---|---|
| **Pest-control operator permit** | Dubai Municipality (and each emirate's municipality) | Annual | Approved-operator permit; keep service records. Only registered pesticides/methods. |
| **Water tank cleaning & disinfection certificate** | Local municipality | ~Every 6 months | Cleaning + disinfection + potable-water quality certification of storage tanks. High criticality (public health). |
| **Fire & life-safety** | Civil Defence (QCD / DCD) | Annual inspection | Fire systems inspection/certification for serviced facilities. |
| **Electrical / DEWA-related** | DEWA (Dubai) / relevant authority | Varies | Where FM covers electrical infrastructure. |

Seed data lives in `fm_aabaan_config/data/fm_compliance_regime_data.xml`.
**Cadences there are sensible defaults — verify against the current
municipality/authority rules for each emirate and contract.**

### Emirate nuance
Each emirate has its own municipality and civil-defence rules; a contract's
applicable regime can differ by branch/emirate. Model emirate on `fm.branch`
and attach regimes to the relevant asset categories.

## 4. Operational practices baked into the platform

- **Asset-centric.** Everything services an `fm.asset` (equipment, tank, AC
  unit, premises) with a category (service line) and location. PPM cadence is a
  property of the category (`default_ppm_frequency_months`).
- **Contract-driven scheduling.** An AMC's visit frequency + skip-weekends +
  preferred technician generate planned **Field Service tasks** across the term
  (rolling horizon via daily cron). Weekend handling matters:
  **the UAE working week is Mon–Fri**; Sat/Sun are pushed to the next working
  day (`skip_weekends`).
- **Severity / priority (P1–P4)** on work orders drives SLA expectations
  (P1 critical → fastest response/resolution). Targets are held on
  `fm.sla.rule` per contract.
- **Bilingual documents.** Job sheets, contracts and certificates render
  **English + Arabic** (`fm_documents`), as is standard for UAE-facing
  paperwork; amounts in AED; TRN shown.
- **Sign-off & CSAT.** Field Service captures completion, customer sign-off and
  rating natively on the task.

## 5. Service catalogue (seed products)

`fm_aabaan_config/data/product_data.xml` seeds billable service products (one
per service line + a comprehensive AMC product). Prices are placeholders in AED
— set real rate cards. These are the recurring/one-off invoice lines.

## 6. Localisation checklist for a fresh deployment

- [ ] Install UAE fiscal localization (`l10n_ae`) and set the 5% VAT tax.
- [ ] Set company **TRN** in the company `vat` field; company currency = **AED**.
- [ ] Upload Aabaan **logo** and set brand colours (`fm_branding` / Settings).
- [ ] Confirm **branches** and per-branch address / phone / licence numbers.
- [ ] Review **compliance regime cadences** against current authority rules.
- [ ] Set real **service product** rate cards.
- [ ] Configure native **SLA policies** to match `fm.sla.rule` targets.
- [ ] Working calendar = **Mon–Fri**, UAE public holidays loaded.
