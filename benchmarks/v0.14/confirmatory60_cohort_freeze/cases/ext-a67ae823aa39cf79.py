    def withdraw(self, person=None, orga: bool = False):
        from pretalx.submission.domain.submission import (  # noqa: PLC0415 -- thin method
            set_submission_state,
        )

        set_submission_state(self, SubmissionStates.WITHDRAWN, person=person, orga=orga)
