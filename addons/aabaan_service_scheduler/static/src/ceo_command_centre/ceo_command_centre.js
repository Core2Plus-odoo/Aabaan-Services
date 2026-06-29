/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CeoCommandCentre extends Component {
    static template = "aabaan_service_scheduler.CeoCommandCentre";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            period: "ytd",
            data: null,
            updatedAt: "",
        });

        this.periods = [
            { value: "ytd", label: "Year to Date" },
            { value: "mtd", label: "Month to Date" },
            { value: "qtd", label: "Quarter to Date" },
            { value: "last_year", label: "Last 12 Months" },
        ];

        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const data = await this.orm.call(
            "aabaan.ceo.dashboard",
            "get_dashboard_data",
            [this.state.period]
        );
        this.state.data = data;
        this.state.updatedAt = new Date().toLocaleTimeString();
        this.state.loading = false;
    }

    onPeriodChange(ev) {
        this.state.period = ev.target.value;
        this.load();
    }

    get greeting() {
        const h = new Date().getHours();
        if (h < 12) {
            return "Good morning";
        }
        if (h < 18) {
            return "Good afternoon";
        }
        return "Good evening";
    }

    get today() {
        return new Date().toLocaleDateString(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    }

    formatMoney(amount) {
        const data = this.state.data;
        const sym = data && data.currency ? data.currency.symbol : "";
        const value = Number(amount || 0).toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        });
        if (data && data.currency && data.currency.position === "after") {
            return `${value} ${sym}`;
        }
        return `${sym} ${value}`;
    }

    // ---- Navigation helpers (open the matching standard views) ----
    openAction(xmlid) {
        this.action.doAction(xmlid);
    }
}

registry.category("actions").add("aabaan_ceo_command_centre", CeoCommandCentre);
