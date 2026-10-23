"""MCPB adapter: explicit configuration, unchanged D2 consent and grant checks."""
import os
import sys


def main():
    policy = os.environ.get("GOLEM_TRANSFER_POLICY", "")
    digest = os.environ.get("GOLEM_REVIEWED_POLICY_SHA256", "")
    consent = os.environ.get("GOLEM_APPROVE_DATA_TRANSFER", "")
    if not policy or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        sys.stderr.write("MCPB_REVIEWED_POLICY_REQUIRED\n")
        return 1
    if consent.lower() != "true":
        sys.stderr.write("OWNER_TRANSFER_APPROVAL_REQUIRED\n")
        return 1
    from integration_mcp import main as serve
    sys.argv = [sys.argv[0], "--policy", policy, "--reviewed-policy-sha256", digest,
                "--approve-data-transfer"]
    return serve()


if __name__ == "__main__":
    sys.exit(main())
