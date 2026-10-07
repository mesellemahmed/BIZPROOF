def _find_affected_charts(
    dataset_id: int, metric_name: str
) -> list[MetricChartReference]:
    """Return only accessible charts on this dataset referencing the metric."""
    from superset import db
    from superset.exceptions import SupersetSecurityException
    from superset.models.slice import Slice
    from superset.utils import json
    from superset.utils.core import DatasourceType

    charts = (
        db.session.query(Slice)
        .filter(
            Slice.datasource_id == dataset_id,
            Slice.datasource_type == DatasourceType.TABLE,
        )
        .order_by(Slice.id)
        .all()
    )
    references = []
    for chart in charts:
        try:
            security_manager.raise_for_access(chart=chart)
        except SupersetSecurityException:
            continue
        configs = [chart.form_data]
        if chart.query_context:
            try:
                configs.append(json.loads(chart.query_context))
            except json.JSONDecodeError:
                # Chart impact is advisory; still inspect valid form data.
                pass
        if _references_metric(configs, metric_name):
            references.append(
                MetricChartReference(
                    id=chart.id,
                    uuid=str(chart.uuid) if chart.uuid else None,
                    slice_name=chart.slice_name,
                )
            )
    return references
