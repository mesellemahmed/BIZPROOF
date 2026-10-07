def set_workflow_step_errors(self, context):
    workflow = context['workflow']
    for step in self.step_errors:
        error_msg = self.step_errors[step]
        workflow.add_error_to_step(error_msg, step)
