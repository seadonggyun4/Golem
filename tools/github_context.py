"""Live candidate identity adapters; no SHA-to-PR or queue-name guessing."""
import re
from urllib.parse import quote

import remote_status as remote


def check(value, code="INVALID_CANDIDATE_CONTEXT"):
    remote.check(value, code)


def sha(value):
    check(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value))
    return value


def ref(value):
    check(isinstance(value, str) and 0 < len(value) <= 1024
          and not any(c in value for c in " ~^:?*[\\")
          and all(32 < ord(c) < 127 for c in value)
          and not any(p in ("", ".", "..") or p.startswith(".") or p.endswith((".", ".lock"))
                      for p in value.split("/")) and ".." not in value and "@{" not in value)
    return value


def validate(value):
    check(isinstance(value, dict))
    if value.get("kind") == "pull_request":
        check(set(value) == {"kind", "number", "ref_mode"}
              and type(value["number"]) is int and value["number"] > 0
              and value["ref_mode"] in ("head", "merge"))
    elif value.get("kind") == "merge_group":
        check(set(value) == {"kind", "run_id", "head_ref", "head_sha", "base_sha"}
              and type(value["run_id"]) is int and value["run_id"] > 0)
        ref(value["head_ref"])
        sha(value["head_sha"]); sha(value["base_sha"])
    else:
        check(False)
    return value


def resolve(client, value, branch, branch_sha):
    """Bind a candidate to live provider identities, not caller claims alone.

    A queue Actions run is required as provider provenance for merge_group;
    a caller-created gh-readonly-queue ref is insufficient. Re-run this function
    after reading analyses to detect candidate/base/queue movement.
    """
    validate(value)
    ref("refs/heads/" + branch)
    repository = client.base.split("/repos/", 1)[1]
    base_ref = "refs/heads/" + branch
    live_base = client.one("/git/ref/" + quote(base_ref.removeprefix("refs/"), safe="/"))
    check(live_base["ref"] == base_ref and live_base["object"]["type"] == "commit"
          and live_base["object"]["sha"] == sha(branch_sha), "CANDIDATE_BASE_REF_CHANGED")
    if value["kind"] == "pull_request":
        number, mode = value["number"], value["ref_mode"]
        pr = client.one(f"/pulls/{number}")
        check(pr["number"] == number and pr["state"] == "open" and not pr["merged"]
              and pr["base"]["repo"]["full_name"].casefold() == repository.casefold()
              and pr["base"]["ref"] == branch and pr["base"]["sha"] == branch_sha,
              "PR_BASE_OR_STATE_CHANGED")
        head = sha(pr["head"]["sha"])
        check(type(pr["head"]["repo"]["id"]) is int and pr["head"]["repo"]["id"] > 0)
        target_ref = f"refs/pull/{number}/{mode}"
        live = client.one("/git/ref/" + target_ref.removeprefix("refs/"))
        candidate = head if mode == "head" else sha(live["object"]["sha"])
        # GitHub can return mergeable=true with merge_commit_sha=null while the
        # canonical merge ref exists. Verify that ref and its exact parents;
        # never invent a merge commit or fall back to head scanning.
        if mode == "merge" and pr.get("merge_commit_sha") is not None:
            check(pr["merge_commit_sha"] == candidate, "PR_MERGE_REF_MISMATCH")
        metadata = {"number": number, "head_sha": head, "base_sha": branch_sha,
                    "head_repository_id": pr["head"]["repo"]["id"]}
        if mode == "merge":
            commit = client.one("/git/commits/" + candidate)
            check(commit["sha"] == candidate and
                  [p["sha"] for p in commit["parents"]] == [branch_sha, head],
                  "PR_MERGE_PARENTS_MISMATCH")
    else:
        target_ref = value["head_ref"]
        check(target_ref.startswith("refs/heads/gh-readonly-queue/" + branch + "/")
              and value["base_sha"] == branch_sha, "MERGE_GROUP_BASE_MISMATCH")
        candidate = value["head_sha"]
        run = client.one(f"/actions/runs/{value['run_id']}")
        check(run["id"] == value["run_id"] and run["event"] == "merge_group"
              and run["head_sha"] == candidate
              and "refs/heads/" + run["head_branch"] == target_ref
              and run["repository"]["full_name"].casefold() == repository.casefold(),
              "MERGE_GROUP_PROVIDER_PROVENANCE_MISMATCH")
        comparison = client.one(f"/compare/{branch_sha}...{candidate}")
        check(comparison["status"] == "ahead"
              and comparison["merge_base_commit"]["sha"] == branch_sha,
              "MERGE_GROUP_BASE_ANCESTRY_MISMATCH")
        metadata = {"run_id": run["id"], "base_sha": branch_sha,
                    "run_attempt": run["run_attempt"], "queue_membership_verified": False}
    live = client.one("/git/ref/" + quote(target_ref.removeprefix("refs/"), safe="/"))
    check(live["ref"] == target_ref and live["object"]["type"] == "commit"
          and live["object"]["sha"] == candidate, "CANDIDATE_REF_CHANGED")
    return {"kind": value["kind"], "ref": target_ref, "sha": candidate,
            **metadata, "current_merge_authorized": False}
