# Aabaan — UAE Setup Runbook (basic + advanced configuration)

Practical, ordered configuration for the live Odoo 19 Enterprise instance
(`core2plus-odoo-aabaan-services.odoo.com`). The **`fm_aabaan_setup`** module
already applies the safe base config (UAE working week, HR departments/jobs,
country). Everything below is done **in the Odoo UI on your instance**, because
it depends on live data, statutory choices, and figures that must not be
guessed.

> Legend: **[SAFE]** anytime · **[CARE]** one-time / irreversible-ish — back up
> (Odoo.sh → Backups) first · **[ENT]** needs an Enterprise app.

---

## 0. Audit first (accounting state) — do this before touching finance

Settings → **Accounting**. Determine which case you are in:

1. **Companies** → is **Country = United Arab Emirates**, **Currency = AED**?
2. Accounting → Configuration → **Chart of Accounts**: are there accounts? Are
   there **posted** journal entries / invoices? (The logs show posted invoices
   and bank reconciliation → **assume accounting is already live**.)
3. Accounting → Configuration → **Taxes**: is there a **5% VAT** (Sales/Purchase)?
4. Company **VAT/TRN** set on the company (`Settings → Companies → Tax ID`)?

**If accounting is already live (most likely): DO NOT reinstall the fiscal
localization / chart of accounts.** Only fill gaps (TRN, 5% tax defaults,
fiscal positions). Reinstalling a CoA on a company with entries corrupts books.

---

## 1. Company & localization

- **[SAFE]** Company: name *Aabaan Services*, **logo** (upload here — flows to
  PDFs), address, phone, **TRN** in *Tax ID*, currency **AED**, country **UAE**.
- **[CARE][ENT]** If (and only if) **no** chart of accounts exists:
  Accounting → Configuration → **Settings → Fiscal Localization = United Arab
  Emirates**, install the package. This loads the UAE CoA + 5% VAT + fiscal
  positions. **Never** do this on a company that already has entries.
- **[SAFE]** Confirm/**create 5% VAT** taxes (Standard Rated 5%), set them as
  the default sale/purchase taxes.
- **[SAFE]** Set the **fiscal year** end (Dec 31) and lock dates as needed.

## 2. Invoicing / FTA compliance

- **[SAFE]** Invoice = FTA **Tax Invoice** once it shows: supplier + **TRN**,
  sequential number, date, customer, line, taxable amount, **VAT 5%**, total,
  AED. Set the **invoice sequence** and add TRN/logo to the layout
  (Settings → Invoicing → *Configure Document Layout*).
- **[SAFE]** Payment terms (e.g. 30 days), and the FM service products' taxes.

## 3. Working week & calendar  *(base module already sets this)*

- **[SAFE]** Employees → Configuration → **Working Schedules**: confirm
  **UAE Standard (Mon–Fri)** is the company default. UAE private-sector weekend
  is **Sat–Sun**. The FM scheduler already skips Fri/Sat if you prefer a
  Sun–Thu field week — adjust `skip_weekends`/the calendar to your policy.

## 4. HR foundation  *(departments & jobs already seeded)*

- **[SAFE]** Employees: create/import staff (name, Emirates ID, passport,
  visa/labour-card expiry, department, job, **working schedule**, manager,
  **branch** via `fm_branch`). Set expiry reminders (Activities) for visa /
  labour card / Emirates ID.
- **[SAFE]** Map your FM technicians to **users** so they appear on work orders
  and the Maintenance Calendar.

## 5. Leaves  *(UAE labour law)*

Time Off app **[ENT/community]**:
- **Annual leave**: 30 calendar days/yr after 1 year (2 days/month between
  6–12 months). Create an *Annual Leave* allocation.
- **Sick leave**: up to 90 days/yr after probation (15 full pay, 30 half, 45
  unpaid) — model as a Sick Leave type with sub-rules or manual approval.
- **Public holidays**: load UAE holidays into the working schedule's *Global
  Time Off* each year (Eid, National Day, etc. — dates set by moon/announcement).
- Maternity, parental, Hajj as per policy.

## 6. Full UAE Payroll  **[ENT]**  *(needs Odoo Enterprise Payroll + your figures)*

> Requires the **Payroll** app and, ideally, the **UAE Payroll localization**
> (`l10n_ae_hr_payroll`) if available on your Enterprise plan. Provide the real
> figures — I will not invent salaries or statutory rates.

1. **Salary structure** (UAE): Basic + **Housing allowance** + **Transport
   allowance** + other allowances; deductions. Confirm your split (e.g. Basic
   60% for gratuity base).
2. **Contracts**: per employee — wage, structure, working schedule, start date.
3. **End-of-Service Gratuity (EOSB)**: 21 days' basic wage per year for the
   first 5 years, 30 days/year thereafter (capped at 2 years' wage); pro-rated,
   subject to resignation rules. Configure as a gratuity rule/provision.
4. **WPS (Wages Protection System)**: capture each employee's **IBAN / bank /
   MOL & agent codes**; generate the **SIF** salary file for the bank. Provide
   the company's **MOL establishment ID, bank routing/agent ID**.
5. **Payslip run**: batch monthly; post to accounting (salary journal); pay via
   the WPS SIF.

**What I need from you to build/seed payroll:** confirm Enterprise Payroll is
available; your **salary structure split** and **allowance policy**; the **WPS
bank/MOL codes**; and whether to seed a standard UAE structure you then adjust.

## 7. Field Service / FM (already built)

- Contracts → Scheduling → **Activate** → visits auto-populate the
  **Maintenance Calendar**. Materials per service → **Material Forecast**.
- Dashboards: **CEO**, **Maintenance Calendar**, Operations/Contracts.

## 8. Master data import (already built)

- **FM → Configuration → Master Data Import** to pull customers/products/
  employees from the old instance (runs server-side).

---

### Suggested order
0 audit → 1 company/localization → 2 invoicing → 3 calendar → 4 HR → 5 leaves →
8 import master data → 6 payroll (with your figures) → verify.

Tell me the **audit results** (§0) and the **payroll figures** (§6) and I'll turn
each codeable piece into the next config module; the rest is the clicks above.
