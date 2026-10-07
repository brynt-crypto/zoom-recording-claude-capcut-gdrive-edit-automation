"""Censor a recording before it is edited: blur boxes, mute windows, verify.

A censor plan (``censor_plan.json``, one per job) says what must not be seen or
heard in a recording — screen regions to blur, spans to silence — plus the crop
that turns the raw capture into the delivered 16:9 picture. From that plan this
package builds the ffmpeg filter, encodes the censored master, maps the windows
onto the rough-cut timeline, and verifies the result frame by frame.

Run it with ``python -m censor <command>``; see ``docs/censoring.md``.
"""
