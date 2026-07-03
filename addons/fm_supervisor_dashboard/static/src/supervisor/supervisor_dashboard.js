/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FmSupervisorDashboard extends Component {
    static template = "fm_supervisor_dashboard.Board";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            data: null,
            monthStart: false,
            technicianId: false,
            serviceLine: false,
            branchId: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("fm.supervisor.dashboard", "get_board_data", [
            this.state.monthStart || null,
            this.state.technicianId || null,
            this.state.serviceLine || null,
            this.state.branchId || null,
        ]);
        this.state.loading = false;
    }

    goMonth(ms) {
        this.state.monthStart = ms;
        this.load();
    }

    onFilter(field, ev) {
        const v = ev.target.value;
        if (field === "technicianId" || field === "branchId") {
            this.state[field] = v ? parseInt(v, 10) : false;
        } else {
            this.state[field] = v || false;
        }
        this.load();
    }

    openVisit(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("fm_supervisor_dashboard", FmSupervisorDashboard);
