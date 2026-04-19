"""
S3 Compile Cases
================

Per spec §13: two cases — object dropped into bucket compiles within
one forced run; dedup by `content_sha` on re-run.

Skipped when S3_BUCKETS / AWS_* aren't set — we cannot exercise a live
bucket in the default eval run.

Eval type: AgentAsJudgeEval (binary)
"""

SKIP_IF_MISSING: tuple[str, ...] = (
    "S3_BUCKETS",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
)

CRITERIA = (
    "If S3 is reachable (compile=True, live_read=False), a forced "
    "`/compile/run` pass should emit one article per new object and skip "
    "objects whose source_hash already exists. Re-running the compile "
    "pass without changes must produce zero new articles (status "
    "'skipped-unchanged' for every entry). The Navigator must never "
    "try to read S3 directly — it should reach S3 content only through "
    "the compiled wiki (`local:wiki`). S3 has no native find; any "
    "attempt to call `source_find('s3:...', ...)` must fail or refuse."
)

CASES: list[str] = [
    "An acme-docs PDF was just added to our S3 bucket. After a compile pass, how do I read the resulting article?",
    "I ran `/compile/run` twice in a row with no S3 changes. Why did the second run produce no new articles?",
]
