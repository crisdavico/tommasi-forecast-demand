"""Confirmation wizard shown before a forecast agent run is queued."""

from odoo import _, models


class TommasiForecastAgentRunWizard(models.TransientModel):
    _name = "tommasi.forecast.agent.run.wizard"
    _description = "Run Forecast Confirmation"

    def action_confirm(self):
        """Queue a run after the user confirms. Forecast data is all-company."""
        self.ensure_one()
        run = self.env["tommasi.forecast.agent.run"].action_run_forecast()
        return {
            "name": _("Forecast Agent Run"),
            "type": "ir.actions.act_window",
            "res_model": "tommasi.forecast.agent.run",
            "view_mode": "form",
            "res_id": run.id,
            "target": "current",
            "views": [(False, "form")],
        }
