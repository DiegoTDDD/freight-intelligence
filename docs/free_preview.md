# Preview without buying a domain or server

For an initial API preview, `render.yaml` selects a Free Docker web service. Render provides
an `onrender.com` address and managed TLS; no purchased domain or manually provisioned VPS
is required. This is a preview option, not a production availability guarantee.

The draft has no paid disk/database and disables automatic redeploys. The first actual
Blueprint creation still deploys a service; it requires the owner's Render account and
explicit deployment authorization. Changes remain local and uncommitted/unpushed. No
account, service or billable resource has been created during preparation.

Authentication is mandatory and Render generates a random API token in its environment.
Do not put the token into URLs, screenshots, Git or shared logs. Obtain it privately in
the service's environment settings after an authorized creation. Health/docs remain public;
data routes require the header. This simple preview uses the shared-key mode; the separate
users-registry Compose configuration remains available for self-managed hosting.

## What this draft includes and does not include

The image contains application code, not local raw/Silver/Gold/models/artifacts. Consequently,
this draft starts the API and its health/docs, but data routes return 503 until a reviewed
small dataset distribution is prepared. It does not publish the full Streamlit dashboard
or transfer local files automatically. Do not describe this draft as a complete hosted app.
The source repository must contain the reviewed changes before Render can build them;
commit/push remain subject to explicit authorization.

Render Free instances spin down after 15 minutes without traffic and can take roughly a
minute to start again. Their writable filesystem is ephemeral and they cannot attach
persistent disks. Usage allowances apply. Avoid adding a payment method or upgrading a
plan as part of this free preview; any requested payment or agreement must be reviewed by
the user. Free is suitable for previews rather than a production availability commitment.

Next owner steps, to be handled with assistance when authorized: create/sign in to Render,
connect the reviewed repository, review the Free Blueprint, and authorize its initial deploy.
No need to buy a domain first. Source publication and any data transfer must be explicit.

Sources checked 2026-11-12: [Render web services](https://render.com/docs/web-services),
[free-plan behavior](https://render.com/docs/free), and
[Blueprint specification](https://render.com/docs/blueprint-spec).

## Full dashboard preview

`deployment/render.dashboard.yaml` describes a separate Free dashboard service. Its Docker
image uses `deployment/Dockerfile.dashboard` and the reviewed small data snapshot prepared
by `python scripts/prepare_dashboard_preview.py`. It does not run ingestion or the full
pipeline. Snapshot preparation refuses an existing destination, checks size bounds and
validates optional scenario forecast/temporal report provenance. The manifest records exact
file hashes. Local absolute metadata input paths are removed from the snapshot.

Only known FAF Gold aggregates, optional matching annual model/evaluation files and the
archived public README can be copied. Raw CSVs, Silver, environment files, API keys and
saved transport scenarios are excluded. Interactive scenario forms remain session-only.
The saved transport-plan view may be unavailable in this public snapshot; it does not
silently replace missing real plans with invented operational costs.

Publication would make this dashboard and its included public analytical aggregates
internet-accessible. It does not provide per-user private dashboard storage. Do not upload
private operational files into a shared preview without reviewing the hosting/privacy model.
Free-plan memory and idle behavior still apply. The account login does not by itself
authorize Git commits, pushes, paid resources or deployment. Review the final snapshot and
configuration before authorizing publication. No account password is needed in source code.
