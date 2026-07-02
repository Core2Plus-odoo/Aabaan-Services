/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FmCeoDashboard extends Component {
    static template = "fm_ceo_dashboard.FmCeoDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, data: null, updatedAt: "", branchId: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("fm.ceo.dashboard", "get_ceo_data", [
            this.state.branchId || null,
        ]);
        this.state.updatedAt = new Date().toLocaleTimeString();
        this.state.loading = false;
    }

    onBranchChange(ev) {
        this.state.branchId = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this.load();
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

    get maxBranch() {
        const b = this.state.data ? this.state.data.by_branch : [];
        return b.length ? Math.max(...b.map((x) => x.value)) : 1;
    }

    get maxOps() {
        const o = this.state.data ? this.state.data.ops : [];
        const m = o.length ? Math.max(...o.map((x) => x.count)) : 1;
        return m || 1;
    }
}

registry.category("actions").add("fm_ceo_dashboard", FmCeoDashboard);
