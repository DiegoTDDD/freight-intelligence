"""Trigger only the configured Render service at an exact tested Git revision."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

SERVICE_ID = "srv-dbqsibuc6qcc738987g0"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def trigger_deploy(hook, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
        raise ValueError("A full tested Git SHA is required")
    url = urllib.parse.urlsplit(hook or "")
    if (
        url.scheme != "https"
        or url.netloc != "api.render.com"
        or url.path != f"/deploy/{SERVICE_ID}"
        or url.fragment
    ):
        raise ValueError("Deploy hook must target the configured Render service over HTTPS")
    query = urllib.parse.parse_qs(url.query)
    if set(query) != {"key"} or len(query["key"]) != 1 or not query["key"][0]:
        raise ValueError("A valid private Render deploy hook is required")
    query = urllib.parse.urlencode({"key": query["key"][0], "ref": revision})
    request = urllib.request.Request(
        urllib.parse.urlunsplit(url._replace(query=query)), data=b"", method="POST"
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            payload = response.read(65537)
        if len(payload) > 65536:
            raise RuntimeError("Deployment response exceeds expected limit")
        deployment = json.loads(payload).get("deploy", {}).get("id")
        if not isinstance(deployment, str) or not re.fullmatch(r"dep-[a-z0-9]+", deployment):
            raise RuntimeError("No deployment id returned; inspect Render before retrying")
        return deployment
    except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError):
        # Never include the secret hook, request URL, or provider response in logs.
        raise RuntimeError(
            "Deployment could not be confirmed; inspect Render before retrying"
        ) from None


def main():
    try:
        deployment = trigger_deploy(
            os.environ.get("RENDER_DEPLOY_HOOK_URL"), os.environ.get("GITHUB_SHA")
        )
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    print(f"Render accepted deployment {deployment} for tested commit {os.environ['GITHUB_SHA']}")


if __name__ == "__main__":
    main()
