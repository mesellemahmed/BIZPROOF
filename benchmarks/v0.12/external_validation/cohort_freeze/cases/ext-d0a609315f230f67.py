def cancel_github_workflows(  # noqa: C901
    branch_or_pull: Optional[str],
    repo: str,
    event: list[str],
    include_last: bool,
    include_running: bool,
) -> None:
    """Cancel running or queued GitHub workflows by branch or pull request ID"""
    if not github_token:
        raise ClickException("Please provide GITHUB_TOKEN as an env variable")

    statuses = ("queued", "in_progress") if include_running else ("queued",)
    events = event
    pr = None

    if branch_or_pull is None:
        title = "all jobs" if include_last else "all duplicate jobs"
    elif branch_or_pull.isdigit():
        pr = get_pull_request(repo, pull_number=branch_or_pull)
        title = f"pull request #{pr['number']} - {pr['title']}"
    else:
        title = f"branch [{branch_or_pull}]"

    print(
        f"\nCancel {'active' if include_running else 'previous'} "
        f"workflow runs for {title}\n"
    )

    if pr:
        runs = get_runs(
            repo,
            statuses=statuses,
            events=event,
            branch=pr["head"]["ref"],
            user=pr["user"]["login"],
        )
    else:
        user = None
        branch = branch_or_pull
        if branch and ":" in branch:
            [user, branch] = branch.split(":", 2)
        runs = get_runs(
            repo,
            branch=branch,
            user=user,
            statuses=statuses,
            events=events,
        )

    # sort old jobs to the front, so to cancel older jobs first
    runs = sorted(runs, key=lambda x: x["created_at"])
    if runs:
        print(
            f"Found {len(runs)} potential runs of\n"
            f"   status: {statuses}\n   event: {events}\n"
        )
    else:
        print(f"No {' or '.join(statuses)} workflow runs found.\n")
        return

    if not include_last:
        # Keep the latest run for each workflow and cancel all others
        seen = set()
        dups = []
        for item in reversed(runs):
            key = f"{item['event']}_{item['head_branch']}_{item['workflow_id']}"
            if key in seen:
                dups.append(item)
            else:
                seen.add(key)
        if not dups:
            print(
                "Only the latest runs are in queue. "
                "Use --include-last to force cancelling them.\n"
            )
            return
        runs = dups[::-1]

    last_sha = None

    print(f"\nCancelling {len(runs)} jobs...\n")
    for entry in runs:
        head_commit = entry["head_commit"]
        if head_commit["id"] != last_sha:
            last_sha = head_commit["id"]
            print("")
            print_commit(head_commit, entry["head_branch"])
        try:
            print(f"[{entry['status']}] {entry['name']}", end="\r")
            cancel_run(repo, entry["id"])
            print(f"[Canceled] {entry['name']}     ")
        except ClickException as error:
            print(f"[Error: {error.message}] {entry['name']}    ")
    print("")
