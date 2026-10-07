def register_servlets(hs: "HomeServer", http_server: HttpServer) -> None:
    ReplicationAddUserAccountDataRestServlet(hs).register(http_server)
    ReplicationAddRoomAccountDataRestServlet(hs).register(http_server)
    ReplicationAddTagRestServlet(hs).register(http_server)
    ReplicationRemoveTagRestServlet(hs).register(http_server)

    if hs.config.experimental.msc3391_enabled:
        ReplicationRemoveUserAccountDataRestServlet(hs).register(http_server)
        ReplicationRemoveRoomAccountDataRestServlet(hs).register(http_server)
