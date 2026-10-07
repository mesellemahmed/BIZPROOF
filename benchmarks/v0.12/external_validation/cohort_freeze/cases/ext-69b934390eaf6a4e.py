def _build_replacement_form_data(
    existing_form_data: dict[str, Any],
    parsed_config: ChartConfig,
    effective_dataset_id: int | None,
    replacement_dataset_id: int | None = None,
) -> dict[str, Any]:
    """Map and merge a replacement config for preview and save paths."""
    new_form_data = map_config_to_form_data(
        parsed_config, dataset_id=effective_dataset_id, include_disabled=True
    )
    new_form_data.pop("_mcp_warnings", None)
    dataset_rebind = replacement_dataset_id is not None
    config_plugin = get_registry().get(parsed_config.chart_type, include_disabled=True)
    if replacement_dataset_id is not None and not (
        config_plugin is not None and config_plugin.strict_dataset_rebind
    ):
        # Drop only the inherited state the replacement dataset cannot
        # resolve, then merge as a same-dataset update. Plugins with a strict
        # rebind contract handle the rebind in merge_update_form_data.
        invalid_keys = _inherited_state_invalid_keys(
            existing_form_data,
            new_form_data,
            parsed_config,
            replacement_dataset_id,
        )
        existing_form_data = {
            key: value
            for key, value in existing_form_data.items()
            if key not in invalid_keys
        }
        dataset_rebind = False
    merge_table_column_config(existing_form_data, new_form_data)
    merge_interactive_pivot_ui_config(existing_form_data, new_form_data)
    merged = _merge_replacement_config(
        existing_form_data,
        new_form_data,
        parsed_config,
        dataset_rebind=dataset_rebind,
    )
    if replacement_dataset_id is not None:
        merged["datasource"] = f"{replacement_dataset_id}__table"
    return merged
