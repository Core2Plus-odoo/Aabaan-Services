/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Aabaan executive dashboard: Overview, Expenses, Cash & Bank.
 *
 * All aggregation and all chart geometry happen on the server (see
 * fm.exec.dashboard). This component picks a period, asks for the numbers,
 * and renders them. It loads no charting library on purpose — CLAUDE.md §4
 * records that OWL dashboards here break on stale asset bundles, and every
 * extra dependency is another way for that to happen.
 */
export class FmExecDashboard extends Component {
    static template = "fm_exec_dashboard.FmExecDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            data: null,
            updatedAt: "",
            branchId: false,
            preset: "this_month",
            dateFrom: "",
            dateTo: "",
            section: "overview",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const custom = this.state.preset === "custom";
            this.state.data = await this.orm.call("fm.exec.dashboard", "get_exec_data", [
                this.state.preset,
                custom ? this.state.dateFrom || null : null,
                custom ? this.state.dateTo || null : null,
                this.state.branchId || null,
            ]);
            // Echo back the window the server resolved, so switching from a
            // preset to Custom starts from the dates just shown, not blanks.
            this.state.dateFrom = this.state.data.period.date_from;
            this.state.dateTo = this.state.data.period.date_to;
            this.state.updatedAt = new Date().toLocaleTimeString();
        } finally {
            this.state.loading = false;
        }
    }

    onPresetChange(ev) {
        this.state.preset = ev.target.value;
        // A custom range means nothing until both ends are set; the dates
        // are already populated from the last load, so this still reloads.
        this.load();
    }

    onDateChange(which, ev) {
        this.state[which === "from" ? "dateFrom" : "dateTo"] = ev.target.value;
        if (this.state.dateFrom && this.state.dateTo) {
            this.load();
        }
    }

    onBranchChange(ev) {
        this.state.branchId = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this.load();
    }

    showSection(section) {
        this.state.section = section;
    }

    // ---------------------------------------------------------------- format
    /** Short-scaled money: a CEO reads 768.2K faster than 768,200. */
    money(value) {
        if (value === false || value === null || value === undefined) {
            return "—";
        }
        const currency = this.state.data ? this.state.data.currency : "";
        const abs = Math.abs(value);
        const sign = value < 0 ? "-" : "";
        if (abs >= 1e6) {
            return `${sign}${currency} ${(abs / 1e6).toFixed(1)}M`;
        }
        if (abs >= 1e3) {
            return `${sign}${currency} ${(abs / 1e3).toFixed(1)}K`;
        }
        return `${sign}${currency} ${abs.toFixed(0)}`;
    }

    /** Full precision, for table cells where the exact figure matters. */
    exact(value) {
        if (value === false || value === null || value === undefined) {
            return "—";
        }
        return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    pct(value, digits = 1) {
        if (value === false || value === null || value === undefined) {
            return "—";
        }
        return `${value.toFixed(digits)}%`;
    }

    /** "+8.4% vs prior period", or a plain statement when there is none. */
    delta(value) {
        if (value === false || value === null || value === undefined) {
            return "no prior period to compare";
        }
        return `${value > 0 ? "+" : ""}${value.toFixed(1)}% vs prior period`;
    }

    /** `inverse` for measures where up is bad — expenses, overdue. */
    deltaClass(value, inverse = false) {
        if (value === false || value === null || value === undefined || value === 0) {
            return "fm-x-flat";
        }
        return (inverse ? value < 0 : value > 0) ? "fm-x-up" : "fm-x-down";
    }

    achvClass(value) {
        if (value === false) {
            return "fm-x-pill fm-x-pill--neutral";
        }
        if (value >= 100) {
            return "fm-x-pill fm-x-pill--good";
        }
        return value >= 90 ? "fm-x-pill fm-x-pill--warn" : "fm-x-pill fm-x-pill--bad";
    }

    /** Height of one segment in a column, as a percentage of the tallest. */
    segment(value, max) {
        return max ? `${(Math.abs(value) / max) * 100}%` : "0%";
    }

    get periodLabel() {
        const p = this.state.data && this.state.data.period;
        return p ? `${p.date_from} → ${p.date_to} · ${p.days} days` : "";
    }
}

registry.category("actions").add("fm_exec_dashboard", FmExecDashboard);
