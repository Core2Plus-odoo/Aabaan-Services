/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FmCommandCentre extends Component {
    static template = "fm_command_centre.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            error: null,
            loading: false,
            tab: "executive",
            period: "this_month",
            // Shell kept from the last successful load so the tab bar and
            // period selector stay on screen while the next tab loads —
            // switching tabs shouldn't blank the whole page.
            shell: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("fm.command.centre", "get_data", [
                this.state.tab,
                this.state.period,
            ]);
            this.state.data = data;
            this.state.shell = {
                tabs: data.tabs,
                periods: data.periods,
                company: data.company,
                as_of: data.as_of,
                range: data.range,
            };
        } catch (error) {
            this.state.data = null;
            this.state.error = String((error && error.message) || error);
        } finally {
            this.state.loading = false;
        }
    }

    selectTab(tab) {
        if (this.state.tab === tab) return;
        this.state.tab = tab;
        this.load();
    }

    selectPeriod(period) {
        if (this.state.period === period) return;
        this.state.period = period;
        this.load();
    }

    refresh() {
        this.load();
    }

    // ---- formatting -------------------------------------------------

    fmt(value) {
        const n = Math.round(value || 0);
        const abs = Math.abs(n);
        if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
        if (abs >= 1e4) return Math.round(n / 1e3).toLocaleString() + "K";
        return n.toLocaleString();
    }

    money(value) {
        return ((this.state.data && this.state.data.currency) || "AED") + " " + this.fmt(value);
    }

    /** A percentage that may legitimately be unknown — null renders as a
     *  dash, never as 0%, which would read as a real measurement. */
    pct(value) {
        return value === null || value === undefined ? "—" : value.toFixed(1) + "%";
    }

    deltaClass(delta, invert) {
        if (delta === null || delta === undefined || delta === 0) return "flat";
        const good = invert ? delta < 0 : delta > 0;
        return good ? "up" : "down";
    }

    deltaText(delta) {
        if (delta === null || delta === undefined) return "";
        const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "–";
        return arrow + " " + Math.abs(delta).toFixed(1) + "%";
    }

    // ---- bar / column geometry --------------------------------------

    barWidth(items, item) {
        const max = Math.max(1, ...items.map((i) => i.gross || 0));
        return Math.max(2, Math.round((100 * (item.gross || 0)) / max));
    }

    barCount(items, item) {
        const max = Math.max(1, ...items.map((i) => i.count || 0));
        return Math.max(2, Math.round((100 * (item.count || 0)) / max));
    }

    barHours(items, item) {
        const max = Math.max(1, ...items.map((i) => i.hours || 0));
        return Math.max(2, Math.round((100 * (item.hours || 0)) / max));
    }

    monthHeight(items, item) {
        const max = Math.max(1, ...items.map((i) => i.gross || 0));
        return Math.max(item.gross ? 4 : 0, Math.round((100 * (item.gross || 0)) / max));
    }

    /** Ring gauge for a percentage KPI, drawn with a conic gradient so no
     *  charting library is needed. */
    ringStyle(value, invert) {
        const v = Math.max(0, Math.min(100, value || 0));
        const good = invert ? v <= 20 : v >= 80;
        const warn = invert ? v <= 50 : v >= 50;
        const color = good ? "#1f9d55" : warn ? "#c98a16" : "#d03b3b";
        return `background: conic-gradient(${color} ${v * 3.6}deg, rgba(20,20,18,.08) 0deg);`;
    }

    hasAny(list) {
        return Array.isArray(list) && list.length > 0;
    }

    someCount(list) {
        return Array.isArray(list) && list.some((i) => i.count);
    }

    // ---- drill-down --------------------------------------------------

    open(item) {
        if (!item || !item.model) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: item.label || "Details",
            res_model: item.model,
            domain: item.domain || [],
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openSub(item) {
        if (!item || !item.model || !item.sub_domain) return;
        this.open({
            model: item.model,
            domain: item.sub_domain,
            label: (item.sub_label || "Details") + " — " + (item.label || ""),
        });
    }

    openRecord(item) {
        if (!item || !item.model || !item.key) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: item.label || "Record",
            res_model: item.model,
            res_id: parseInt(item.key, 10),
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("fm_command_centre", FmCommandCentre);
