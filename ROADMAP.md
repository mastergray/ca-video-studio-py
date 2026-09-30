# CA Video Generator Roadmap

This roadmap records the intended implementation order beyond the capabilities
already described in the product specification. Milestones should preserve
deterministic preview/export parity and keep simulation behavior separate from
visual effects.

## Completed foundation

- Native PySide6 editor with project persistence, preview transport, layer
  management, and background MP4 rendering.
- Independent deterministic 2D, Wolfram 2D, outer-totalistic 3D, and extruded
  Wolfram 3D layers.
- Global project seed with optional per-layer seed overrides.
- Fixed, wrapped, geometric, explicit-cell, RLE, and Wolfram initializers,
  including supported 2D and 3D seed offsets.
- Isometric and camera-projected 3D rendering.
- Per-layer opacity, deterministic fade rate, and time-based 2D trails with a
  separate trail color.
- Native solid and editable state-gradient coloring for 2D layers, including
  deterministic fade and trail interaction.
- Preview resolution and frame rate decoupled from offline export settings.

## Milestone 1 — 2D state gradients (completed 2026-09-29)

Add independent color treatment for every 2D layer.

- Add solid and state-gradient color modes.
- Support editable gradient stops across Generations states.
- Preserve the last state color while a cell fades out.
- Keep trail color independent from the live/state gradient.
- Apply identical color sampling in preview and export.
- Add configuration, UI, renderer, round-trip, and deterministic frame tests.

## Milestone 2 — Cell geometry controls

Complete the remaining 2D raster-layout controls.

- Add a per-cell gap from 0 through 25% of logical cell size.
- Add horizontal alignment: left, center, and right.
- Add vertical alignment: top, center, and bottom.
- Define alignment behavior for `fit` and center-crop behavior for `cover`.
- Ensure geometry is derived from export dimensions and reused by the capped
  preview.
- Test odd dimensions, non-square grids, and edge clipping.

## Milestone 3 — Custom 3D rules

Remove the remaining catalog-only limitation for outer-totalistic 3D layers.

- Add custom B/S/C notation entry.
- Add Moore and von Neumann neighborhood selection.
- Validate neighbor counts against the selected 3D neighborhood.
- Preserve catalog presets while allowing a layer to switch cleanly between a
  preset and a custom rule.
- Add editor, persistence, simulation, and validation tests.

## Milestone 4 — Timeline and compatibility

Complete deterministic project-time controls and legacy ingestion.

- Add optional start and end holds included within total duration.
- Add the `rotate_camera_at_end` hold behavior.
- Add deterministic restart-and-simulate timeline scrubbing.
- Implement migration from the supported proof-of-concept JSON format.
- Report migration assumptions and timing conversions clearly.

## Milestone 5 — Hardening and delivery

Prepare the application for repeatable long-form use on the target system.

- Add reviewed golden-frame fixtures for representative 2D, Wolfram, 3D, and
  mixed-layer projects.
- Run and document the 1920×1080, 30 fps, 60-second stress fixture.
- Profile simulation, surface extraction, projection, composition, and FFmpeg
  streaming before applying targeted optimizations.
- Verify deterministic decoded-frame hashes across repeated renders.
- Expand example projects and end-user documentation.
- Package a one-command local installation and launch workflow.

## Effect scope

- Visual effects are configured per layer unless explicitly documented as a
  canvas effect.
- A background automaton is a normal low-`z_index` layer and may use different
  fade, trail, color, and future effect settings from foreground layers.
- The canvas background remains a solid fill until a separate canvas-effects
  milestone is approved.
- Effects must run in the shared rendering pipeline, not only as Qt widget
  effects, so preview and exported video remain equivalent.

## Deferred scope

- MIDI, HTTP/SSE events, collisions, and event-driven mutations.
- Audio synthesis, audio-reactive behavior, and audio muxing.
- Blend modes beyond normal source-over composition.
- Non-cubic 3D grids.
- Arbitrary user-provided Python or JavaScript.
- New non-CA renderers such as ribbons or procedural forms unless separately
  specified and approved.

The detailed product contract remains in
[`docs/ca-video-spec.md`](docs/ca-video-spec.md), and native editor behavior is
defined in [`docs/native-ui-design.md`](docs/native-ui-design.md).
