{
    "name": "Tommasi Forecast Demand",
    "version": "15.0.5.0.0",
    "category": "Inventory/Product",
    "summary": "MCP tool returning paginated sold-storable demand envelopes",
    "author": "Eynes SRL",
    "license": "AGPL-3",
    "website": "https://gitlab.e-mips.com.ar/tommasi",
    "depends": ["llm_tool", "llm_mcp_server", "sale_stock"],
    "data": [
        "security/forecast_agent_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_forecast_agent.xml",
        "views/forecast_agent_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
