import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "deploy_dashboard", Path(__file__).resolve().parents[1] / "scripts/deploy_dashboard.py"
)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
REVISION = "a" * 40
HOOK = f"https://api.render.com/deploy/{deploy.SERVICE_ID}?key=private-test-key"


def test_only_exact_tested_commit_is_deployed(monkeypatch):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return json.dumps({"deploy": {"id": "dep-test123"}}).encode()

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            return Response()

    monkeypatch.setattr(deploy.urllib.request, "build_opener", lambda *a: Opener())
    assert deploy.trigger_deploy(HOOK, REVISION) == "dep-test123"
    assert f"ref={REVISION}" in requests[0].full_url
    assert requests[0].method == "POST"


@pytest.mark.parametrize(
    "hook",
    [
        None,
        "https://other.example/deploy?key=x",
        HOOK.replace(deploy.SERVICE_ID, "srv-other"),
        HOOK.replace("https:", "http:"),
    ],
)
def test_missing_or_unexpected_service_never_receives_credentials(hook, monkeypatch):
    monkeypatch.setattr(deploy.urllib.request, "build_opener", lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError):
        deploy.trigger_deploy(hook, REVISION)


def test_provider_failure_never_exposes_hook_secret(monkeypatch):
    class Opener:
        def open(self, request, timeout):
            raise OSError(request.full_url)

    monkeypatch.setattr(deploy.urllib.request, "build_opener", lambda *a: Opener())
    with pytest.raises(RuntimeError) as error:
        deploy.trigger_deploy(HOOK, REVISION)
    assert "private-test-key" not in str(error.value)
