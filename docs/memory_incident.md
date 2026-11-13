# Hosted dashboard memory incident — 2026-11-13

Render reported a memory-limit restart. The email alone does not identify the
allocation responsible; provider logs were not retrieved during this investigation.
Local reproduction with the shipped image established a significant pressure source.

The analytics cache loaded all 917,800 corridor rows (31.51 MiB uncompressed) and
`cache_data` deserialized the whole frame for each session and rerun. The UI only
displayed the latest year's top 20. Six real WebSocket sessions with three renders
each approached the 512 MiB cgroup limit. Limiting numerical threads alone did not
provide adequate headroom.

The reader now filters the latest year and selects the top 20 before collecting
and caching. Source files and API coverage remain intact. Solver imports are
deferred until optimization is requested. The hosted image limits numerical thread
pools and keeps disconnected session state for 30 seconds instead of 120.

The corrected image passed the same six-session/18-render scenario: sampled memory
approximately 220–234 MiB, cgroup peak 235.9 MiB, zero OOM events. The probe includes
its own client process, and runs in the same read-only, offline 512 MiB container
used for HTTP checks. CI now runs this scenario, requiring sampled memory below
420 MiB and no OOM kills. This is bounded regression coverage, not an unlimited
traffic or availability guarantee. Solver use and other workspaces can have
different peaks.

`tests/test_dashboard_memory.py` verifies that early filtering preserves the
displayed ranking. `scripts/check_dashboard_sessions.py` exercises actual shared
server sessions rather than separate AppTest processes.
