def validate_answer_option_identifier_unique(*, question, identifier, instance=None):
    _validate_identifier_unique(
        qs=question.options.all(),
        identifier=identifier,
        instance=instance,
        message=_("This identifier is already used for a different option."),
    )
