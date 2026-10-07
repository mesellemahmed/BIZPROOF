def predict_correspondent(self, content: str) -> int | None:
    if self.correspondent_classifier:
        X = self._vectorize(content)
        predicted_id = _predict_with_threshold(
            self.correspondent_classifier,
            X,
            settings.CLASSIFIER_MATCH_THRESHOLD,
        )
        return predicted_id
    return None
