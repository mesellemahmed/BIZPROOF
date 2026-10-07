def submission_filters(context):
    return [
        SearchFilter(search=submission_search, fulltext=True),
        SubmissionStateFilter(name="state", label=_("State"), with_counts=True),
        BooleanFilter(
            name="pending_state__isnull",
            label=_("Pending state changes"),
            yes_label=_("Without"),
            no_label=_("With"),
        ),
        ModelMultiChoiceFilter(
            name="submission_type",
            label=_("Session type"),
            min_choices=2,
            color_field="",
            with_counts=True,
            count_attr="submission_count",
            queryset=lambda bound: annotate_submission_count(
                bound.event.submission_types.all(),
                states=bound.context.get("usable_states"),
            ),
        ),
        TrackFilter(
            name="track",
            label=_("Track"),
            with_counts=True,
            count_attr="submission_count",
        ),
        ModelMultiChoiceFilter(
            name="tags",
            label=_("Tags"),
            with_counts=True,
            count_attr="submission_count",
            distinct=True,
            queryset=lambda bound: annotate_submission_count(bound.event.tags.all()),
        ),
        MultiChoiceFilter(
            name="content_locale",
            label=_("Language"),
            min_choices=2,
            with_counts=True,
            choices=_locale_choices,
        ),
        BooleanFilter(name="is_featured", label=_("Featured")),
        BooleanFilter(name="do_not_record", label=_("Do not record")),
        RequiresSignupFilter(name="requires_signup", label=_("Requires signup")),
        PendingInvitationsFilter(
            name="has_pending_invitations", label=_("Pending invitations")
        ),
    ]
