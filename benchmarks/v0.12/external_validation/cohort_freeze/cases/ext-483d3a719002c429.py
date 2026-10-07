def _build_sequence(g) -> None:
    ids = [p[0] for p in PARTICIPANTS]

    # --- participant headers, ordered left-to-right on the top rank ---------- #
    with g.subgraph() as top:
        top.attr(rank="same")
        for pid, title, sub, theme in PARTICIPANTS:
            _header(top, pid, title, sub, theme)
    for a, b in zip(ids, ids[1:]):
        g.edge(f"{a}__h", f"{b}__h", style="invis")

    # --- one rank per step; way-points on every lifeline, box on the actor --- #
    for i, step in enumerate(STEPS):
        with g.subgraph() as row:
            row.attr(rank="same")
            for pid, _, _, theme in PARTICIPANTS:
                nid = f"{pid}__{i}"
                if step["kind"] == "self" and step["actor"] == pid:
                    _activation(row, nid, i + 1, step["text"], step.get("theme", theme))
                else:
                    _waypoint(row, nid)

    # --- dashed vertical lifelines through the way-points -------------------- #
    for pid, *_ in PARTICIPANTS:
        chain = [f"{pid}__h"] + [f"{pid}__{i}" for i in range(len(STEPS))]
        for a, b in zip(chain, chain[1:]):
            g.edge(a, b, style="dashed", arrowhead="none", color=LIFELINE, penwidth="1.3")

    # --- message arrows (horizontal, do not constrain ranking) --------------- #
    for i, step in enumerate(STEPS):
        if step["kind"] != "msg":
            continue
        g.edge(
            f"{step['from']}__{i}",
            f"{step['to']}__{i}",
            xlabel=_edge_label(i + 1, step["label"]),
            color=step["color"],
            fontcolor=step["color"],
            style=step.get("style", "solid"),
            arrowhead="vee",
            penwidth="2",
            constraint="false",
        )

    _legend(g)
