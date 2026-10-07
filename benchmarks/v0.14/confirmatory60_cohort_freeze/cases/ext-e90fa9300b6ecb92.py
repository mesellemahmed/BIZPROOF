def version(self):
    return request.make_json_response({
        'version_info': odoo.release.version_info,
        'version': odoo.release.version,
    })
