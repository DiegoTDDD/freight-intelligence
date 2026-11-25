"""Exercise the independent public image offline and without private local mounts."""

import argparse
import subprocess
import uuid

PROBE = r'''
import json,time,urllib.request,urllib.error
base='http://127.0.0.1:8000'
deadline=time.monotonic()+45
while True:
    try:
        with urllib.request.urlopen(base+'/ready',timeout=2) as r: assert r.status==200
        break
    except OSError:
        if time.monotonic()>deadline:raise RuntimeError('Independent API did not start')
        time.sleep(.25)
with urllib.request.urlopen(base+'/version',timeout=5) as r:
    version=json.load(r)
    assert version['service']=='loginexus-public-api' and version['revision']=='a'*40
for path in ('/docs','/annual-kpis','/annual-forecast','/brazil/indicators?mode=rail',
             '/brazil/gas-movements','/brazil/road-state-pairs?origin_state=SP',
             '/brazil/inland-transport?view=commodities&limit=1','/brazil/air-freight?view=pairs&limit=1',
             '/brazil/duty-review?example=unknown_regime'):
    with urllib.request.urlopen(base+path,timeout=10) as r: assert r.status==200,path
try:urllib.request.urlopen(base+'/transport-plan',timeout=5)
except urllib.error.HTTPError as error:assert error.code==503
else:raise AssertionError('Private business plan exposed')
print('Independent public API HTTP/data/private-plan checks passed offline within 512 MiB')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    name = "loginexus-public-check-" + uuid.uuid4().hex[:12]
    try:
        subprocess.run(["docker", "run", "-d", "--name", name, "--network", "none", "--read-only",
                        "--memory", "512m", "--cpus", "1", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                        "--tmpfs", "/tmp:rw,nosuid,size=64m", "--env", "LOGINEXUS_BUILD_REVISION=" + "a" * 40,
                        args.image], check=True, timeout=60, stdout=subprocess.DEVNULL)
        subprocess.run(["docker", "exec", name, "python", "-c", PROBE], check=True, timeout=90)
        subprocess.run(["docker", "exec", name, "python", "-c",
                        "import sys,freight_intelligence.public_api; assert 'streamlit' not in sys.modules"], check=True, timeout=30)
    finally:
        subprocess.run(["docker", "rm", "-f", name], timeout=30, check=False, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
