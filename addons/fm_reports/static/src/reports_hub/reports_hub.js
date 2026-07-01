/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Catalog of report/analysis shortcuts, grouped per brief §7.7. Each entry's
// `action` is an action XML id opened via the action service.
const CATALOG = [
    {
        section: "Operational",
        cards: [
            { title: "Work Orders", desc: "All Field Service work orders by stage, severity and technician.", icon: "fa-wrench", action: "fm_fsm.action_fm_workorders" },
            { title: "Asset Registry", desc: "Assets by location, criticality and service line.", icon: "fa-cubes", action: "fm_asset.action_fm_asset" },
        ],
    },
    {
        section: "Financial",
        cards: [
            { title: "Contracts", desc: "AMC/break-fix contracts, ACV/TCV and health.", icon: "fa-file-text-o", action: "fm_contract.action_fm_contract" },
        ],
    },
    {
        section: "Compliance & Audit",
        cards: [
            { title: "Certificates", desc: "Compliance certificates and expiry status.", icon: "fa-certificate", action: "fm_compliance.action_fm_compliance_certificate" },
            { title: "Regimes", desc: "Regulatory regimes and task templates.", icon: "fa-balance-scale", action: "fm_compliance.action_fm_compliance_regime" },
        ],
    },
];

export class FmReportsHub extends Component {
    static template = "fm_reports.FmReportsHub";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.catalog = CATALOG;
    }

    open(actionXmlId) {
        this.action.doAction(actionXmlId);
    }
}

registry.category("actions").add("fm_reports_hub", FmReportsHub);
