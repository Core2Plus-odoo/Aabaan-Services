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
            expanded: {},
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

    /** Show every visit of a day in its own cell, or fold it back to three. */
    toggleDay(dateStr) {
        this.state.expanded[dateStr] = !this.state.expanded[dateStr];
    }

    goMonth(ms) {
        this.state.monthStart = ms;
        this.load();
    }

    onPeriod(field, ev) {
        const y = field === "year" ? parseInt(ev.target.value, 10) : this.state.data.year;
        const m = field === "month" ? parseInt(ev.target.value, 10) : this.state.data.month_num;
        this.goMonth(`${y}-${String(m).padStart(2, "0")}-01`);
    }

    openDay(dateStr) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Visits — " + dateStr,
            res_model: "project.task",
            domain: [
                ["fm_wo_type", "!=", false],
                ["date_deadline", ">=", dateStr + " 00:00:00"],
                ["date_deadline", "<=", dateStr + " 23:59:59"],
            ],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    /** Open exactly the visits a KPI card or legend row counted. */
    openIds(label, ids) {
        if (!ids || !ids.length) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: label + " — " + this.state.data.month_label,
            res_model: "project.task",
            domain: [["id", "in", ids]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    /** The day's visits as a list — the same ones the cell shows, so the
     *  technician / service / branch filters carry over. */
    openDayList(cell) {
        const ids = cell.events.map((e) => e.id);
        if (!ids.length) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Visits — " + cell.date,
            res_model: "project.task",
            domain: [["id", "in", ids]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    /** Every visit of the month, under the current filters, as Excel. */
    async exportExcel() {
        const res = await this.orm.call("fm.supervisor.dashboard", "export_board_xlsx", [
            this.state.monthStart || null,
            this.state.technicianId || null,
            this.state.serviceLine || null,
            this.state.branchId || null,
        ]);
        const bytes = Uint8Array.from(atob(res.content), (ch) => ch.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }));
        const link = document.createElement("a");
        link.href = url;
        link.download = res.filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    print() {
        window.print();
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
