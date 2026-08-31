"""jobradar core: collect → dedup → filter → scoring → notification.

Each module is one layer of the pipeline: `http` (transport), `text` (HTML/date
cleaning), `dedup` (merge key), `filters` (L0), `db` (schema/log),
`collectors/*` (sources), `scoring` (L1), `notify` (Telegram), `pipeline`
(orchestration). Everything used to live in one engine.py; here it's split along
the seams (ADR-0006).
"""
