def get_infrastructure_name(self):
    # Include flow and flow_run details
    flow_name = getattr(self.flow, "name", "unknown-flow")
    flow_run_id = getattr(self.flow_run, "id", "no-flowrun")
    return f"{flow_name}-{flow_run_id}-{self.name}-{self.run_id}"