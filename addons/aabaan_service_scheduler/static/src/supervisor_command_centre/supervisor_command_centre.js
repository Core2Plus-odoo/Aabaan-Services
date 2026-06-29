/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SupervisorCommandCentre extends Component {
    static template = "aabaan_service_scheduler.SupervisorCommandCentre";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            data: null,
            updatedAt: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "aabaan.supervisor.dashboard",
            "get_dashboard_data",
            []
        );
        this.state.updatedAt = new Date().toLocaleTimeString();
        this.state.loading = false;
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

    openAction(xmlid) {
        this.action.doAction(xmlid);
    }
}

registry.category("actions").add("aabaan_supervisor_command_centre", SupervisorCommandCentre);
