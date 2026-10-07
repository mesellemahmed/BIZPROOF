def build_extension_data(extension: LoadedExtension) -> dict[str, Any]:
    manifest = extension.manifest
    extension_data: dict[str, Any] = {
        "id": manifest.id,
        "publisher": manifest.publisher,
        "name": extension.name,
        "version": extension.version,
        "description": manifest.description or "",
        "dependencies": manifest.dependencies,
    }
    if manifest.frontend:
        frontend = manifest.frontend
        remote_entry_url = (
            f"/api/v1/extensions/{manifest.publisher}/"
            f"{manifest.name}/{frontend.remoteEntry}"
        )
        extension_data.update(
            {
                "remoteEntry": remote_entry_url,
                "moduleFederationName": frontend.moduleFederationName,
            }
        )
    return extension_data
