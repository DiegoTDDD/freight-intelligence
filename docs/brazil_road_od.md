# Reviewed ANTT state origin–destination movements

The 2025 panel population contains **775 reported pairs**, **28 origin categories**
and **28 destination categories**, totalling **1,368,627,704 published integer
tonnes**. Both sets of independently captured margins reconcile exactly, with
zero residual for every category. EX is the source's exterior category, alongside
the 27 Brazilian UFs. Paid and own-account transport are both included.

Source: [ANTT movement catalogue](https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc/movimentacao-de-cargas),
linked Power BI **Origem|Destino**, page 6/15. Reviewed on 2026-11-19.
Select 2025 only, leave cargo, vehicle, destination and account categories
unfiltered, and select one origin UF at a time. The full filter contract, exact
source URL and file hashes are in
[state_od_provenance.json](../deployment/brazil_road/state_od_provenance.json).

Each origin's rendered destination values are archived as accessibility text.
Tiny treemap tiles can disappear: the detailed **Show as table** rows recover
their published values. For example, TO→AC is 47 tonnes and RN→EX is 138 tonnes.
Acquisition rejected mixed selections and intermediate filter updates through
independent margin checks. The JSON capture is an archived UI transcription,
not an upstream bulk download; displayed integer precision is retained.

The source files and transcription are pinned by a review contract whose SHA-256
is fixed in the reader. Changing the data and updating its manifest does not
authorize a new edition. Rebuild the small derived CSV with
`python -m scripts.prepare_brazil_road_od`. This does not run the FAF pipeline.

## Interpretation and interface

These are reported aggregate MDF-e movements, not unique cargo, individual
trips, navigable geometry or truck dispatch permission. Same-state flows can
cross municipalities; the documented within-municipality and other MDF-e
exemptions still apply. Nine of the 784 possible category pairs are unlisted;
they are not imputed as zero. The 16 archived yearbook RGI pairs remain a
separate, more geographically detailed source population and edition.

The displayed update stamp is still “mar/26”; it is preserved as source metadata
and does not establish freshness. This snapshot is specifically the reviewed
2025 edition, not live tracking.

In **Brazilian freight → All five modes → Road**, select **State
origin–destination tonnes · 2025**. Filter origin, destination and same/different
state. The chart displays the largest 20 matching pairs; the table and CSV retain
every matching observation. English is the default, Portuguese is optional.

`GET /api/brazil/road-state-pairs` provides bounded pagination (`limit` 1–500,
default 100; nonnegative `offset`). Optional `origin_state`, `destination_state`
accept the 27 UFs and EX; `same_state` is boolean. `year` accepts only 2025.
`filtered_tonnes` covers all matching rows, independently of pagination;
metadata totals always describe the full snapshot. The existing analytics role
protects private deployments; the hosted public mode serves public snapshots.

Example: `/api/brazil/road-state-pairs?origin_state=SP&destination_state=MG`
returns one reported pair, **20,814,789 tonnes**. Invalid filters return 422;
missing or modified evidence makes this endpoint unavailable with 503.
