def _get_applicable_task_states(self):
    """
    Returns the set of task states whose status applies to the current revision.
    """
    task_states = TaskState.objects.filter(workflow_state_id=self.id)
    # If WAGTAIL_WORKFLOW_REQUIRE_REAPPROVAL_ON_EDIT=True, this is only task states created on the current revision
    if getattr(settings, "WAGTAIL_WORKFLOW_REQUIRE_REAPPROVAL_ON_EDIT", False):
        latest_revision_id = (
            self.revisions()
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)
            .first()
        )
        task_states = task_states.filter(revision_id=latest_revision_id)
    return task_states
