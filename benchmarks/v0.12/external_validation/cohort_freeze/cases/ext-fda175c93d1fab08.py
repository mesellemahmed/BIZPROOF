    def _pie_chart_spec(
        self, fields: List[str], field_types: Dict[str, str] | None = None
    ) -> Dict[str, Any]:
        """Create pie chart specification using arc marks."""
        field_types = field_types or {}
        category_field = fields[0] if fields else "category"
        value_field = fields[1] if len(fields) > 1 else fields[0] if fields else "value"

        return {
            "mark": {"type": "arc", "tooltip": True},
            "encoding": {
                "theta": {
                    "field": value_field,
                    "type": field_types.get(value_field, "quantitative"),
                },
                "color": {
                    "field": category_field,
                    "type": field_types.get(category_field, "nominal"),
                    "title": category_field,
                },
                "tooltip": [
                    {"field": f, "type": field_types.get(f, "nominal")}
                    for f in fields[:5]
                ],
            },
        }
