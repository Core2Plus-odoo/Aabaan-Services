/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FmExecDashboard extends Component {
    static template = "fm_dashboards.FmExecDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, data: null, updatedAt: "" });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("fm.dashboard.exec", "get_dashboard_data", []);
        this.state.updatedAt = new Date().toLocaleTimeString();
        this.state.loading = false;
    }

    get greeting() {
        const h = new Date().getHours();
        return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    }

    get today() {
        return new Date().toLocaleDateString(undefined, {
            weekday: "long", day: "numeric", month: "long", year: "numeric",
        });
    }

    money(v) {
        const sym = this.state.data ? this.state.data.currency : "";
        return `${sym} ${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
}

registry.category("actions").add("fm_exec_dashboard", FmExecDashboard);
