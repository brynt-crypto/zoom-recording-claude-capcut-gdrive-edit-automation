"""Narration audio -> TED-Ed-style animated CapCut draft.

Pipeline: audio -> whisper transcript -> Claude-authored storyboard.json ->
Google Imagen stills -> CapCut draft (still images + Ken Burns motion + the
user's narration as the audio track + per-scene captions).
"""
