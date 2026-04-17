"""
Drive Live-Read Cases — Phase 1
===============================

Per spec §10: Drive-backed queries cite Drive permalinks with section info.

These cases assume the GoogleDriveSource is configured; if it isn't, the
test should still PASS by virtue of the manifest-refusal behaviour
covered in evals/cases/manifest.py. The criteria here only apply when
the source IS reachable.

Eval type: AgentAsJudgeEval (binary)
"""

SKIP_IF_MISSING: tuple[str, ...] = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_PROJECT_ID",
    "GOOGLE_DRIVE_FOLDER_IDS",
)

CRITERIA = (
    "If Drive is reachable in the manifest, the response should cite a "
    "Drive permalink (https://drive.google.com/...) for any content drawn "
    "from Drive, ideally with the file name and a section pointer. "
    "If Drive is NOT reachable, the response must explicitly say so "
    "rather than fabricating content. Either path passes; silent "
    "fabrication fails."
)

CASES: list[str] = [
    "Find the engineering OKRs document in Drive and give me a one-paragraph summary.",
    "What's in the most recently modified file in our shared Drive folder?",
    "Search Drive for 'data retention' and quote the relevant section.",
]
