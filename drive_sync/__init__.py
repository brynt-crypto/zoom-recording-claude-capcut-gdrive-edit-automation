"""Thin Google Drive (Drive-for-Desktop) layer for the /scan pipeline.

Drive for Desktop mounts the account at G:\\, so everything here is plain local
file I/O — no OAuth, no API. Three jobs:

  scan    list new Zoom recordings in the input folder (vs the ledger)
  ingest  copy a chosen recording into assets/to_edit under a clean job name
  upload  copy an exported edit into the team Drive folder (Drive syncs it up)

State lives in drive_sync/state.json. To remove this feature entirely, delete
the drive_sync/ folder and .claude/commands/scan.md — nothing else is touched.
"""
