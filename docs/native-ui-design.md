# CA Video Generator — Native UI Design

Status: Approved direction for implementation
Version: 0.1
Date: 2026-09-26

## 1. Purpose

This document translates the useful interaction patterns from the
`midi-ca-server-2` Web UI into a native PySide6 desktop application. It defines
the target layout, control organization, and behavior for the editor milestone.
It does not change the simulation or output contracts in
`docs/ca-video-spec.md`.

The native application should feel recognizably related to the reference UI:
a dark canvas-focused workspace, teal accents, compact controls, grouped
settings, immediate visual feedback, and an uncluttered playback mode. It must
still behave like a desktop editor, with native menus, project files, keyboard
shortcuts, resizable panes, and background render jobs.

## 2. Reference UI inventory

The reference application exposes four browser pages. Their useful roles map to
the native application as follows:

| Reference page | Useful behavior | Native destination |
| --- | --- | --- |
| Canvas (`index.html`) | Full-window animation with no editing chrome | Preview-only mode in the main window; full-screen is optional |
| Explorer (`preview.html`) | Live layer experiments, transport, and a compact statistics HUD | Main editor workspace with layer list, inspector, preview, and transport |
| Scenes (`scenes.html`) | Browse, create, edit, and load named configurations | File > New/Open, recent projects, and reusable project presets |
| Scene editor (`scene-edit.html`) | Grouped settings, repeatable entries, contextual fields, inline help, and save feedback | Project/layer inspectors with collapsible sections and native validation |

### 2.1 Patterns to retain

- The preview is visually dominant.
- Controls are grouped by meaning rather than presented as raw JSON.
- Irrelevant controls disappear when dimension or rule type changes.
- Rule and palette choices are named, categorized, and described.
- Play, pause, step, and reset remain adjacent to the preview.
- Generation, population, and density are visible while experimenting.
- Dark neutral surfaces use a restrained teal accent and clear error color.
- Layer settings update the preview with minimal ceremony.
- Advanced groups can collapse so common controls stay easy to scan.

### 2.2 Patterns to adapt

- Fixed Layer A and Layer B forms become an ordered, variable-length layer
  list.
- Foreground/background becomes numeric layer order controlled by drag/drop or
  move buttons.
- Foreground/background speed becomes a per-layer step interval.
- The Web UI's channel color and palette fields become layer appearance
  settings.
- Seed radius becomes one option within a general Initial Condition section.
- Scene names become project names stored in `.cav.json` files.
- The raw JSON preview becomes an optional read-only Project JSON dialog, not a
  permanent part of the main workspace.
- Web status toasts become status-bar messages and native validation feedback.

### 2.3 Patterns to exclude

The following controls exist only to support the reference server's live event
model and must not appear in the version 1 UI:

- MIDI channel number and channel action type.
- Event filters and event values.
- Target-channel routing.
- Collisions and collision types.
- Destroy and control events.
- Mutation chance.
- Generations per event.
- Save-and-load into a running server.
- Server, connection, SSE, and forwarding status.

## 3. Desktop information architecture

The application uses one `QMainWindow` and two workspace presentations:

1. **Editor mode** is the default and exposes authoring controls around the
   preview.
2. **Preview-only mode** hides the sidebars and editor details while preserving
   transport and the HUD. It may also be placed full-screen.

Project management and rendering are desktop actions, not separate pages.
Dialogs are reserved for operations that require focused attention: New
Project, Render Video, Preferences, project validation details, and unsaved
changes.

### 3.1 Main editor layout

The design target at 1280×720 is:

```text
+----------------------------------------------------------------------------+
| File  Edit  View  Playback  Render  Help                   project-name *  |
+----------------------------------------------------------------------------+
| [New] [Open] [Save]       [Editor] [Preview Only]             [Render MP4] |
+------------------+--------------------------------------+------------------+
| LAYERS           |                                      | INSPECTOR        |
|                  |                                      | [Layer][Project] |
| ☑ Layer 2   2D  |          16:9 LIVE PREVIEW           |                  |
| ☑ Layer 1   2D  |                                      | Simulation       |
|                  |                                      |  Dimension       |
| +  Duplicate     |                                      |  Rule family     |
| ↑  ↓  Delete     |                                      |  Rule            |
|                  |                                      |                  |
|                  |                                      | Initial condition|
|                  |                                      | Appearance       |
|                  |                                      | Timing           |
+------------------+--------------------------------------+------------------+
|  |<  [Play/Pause]  [Step]  [Reset]   00:00.00 / 00:10.00   Preview: Fit  |
| Gen 42  |  1,284 live  |  5.9%  |  160×90  |  Life B3/S23  |  Valid       |
+----------------------------------------------------------------------------+
```

This is a spatial contract rather than a pixel-perfect mockup:

- The center preview always receives the largest share of resized space.
- The layer pane defaults to approximately 220 px wide.
- The inspector defaults to approximately 300 px wide and scrolls vertically.
- Both side panes can be resized and hidden from the View menu.
- At 1280×720, the preview remains fully visible with a 16:9 fit and no
  horizontal scrolling in the main window.
- Pane widths and visibility are restored with window geometry, subject to
  safe on-screen bounds.

### 3.2 Preview-only mode

Preview-only mode retains the reference Canvas page's emphasis:

```text
+----------------------------------------------------------------------------+
|                                                                            |
|                             16:9 PREVIEW                                   |
|                                                                            |
+----------------------------------------------------------------------------+
| [Play/Pause]  [Step]  [Reset]  00:00.00 / 00:10.00  Gen 42  1,284 live  |
+----------------------------------------------------------------------------+
```

The menu bar, toolbar, side panes, diagnostics, and editing affordances are
hidden. `Escape` exits full-screen or returns to editor mode. Preview-only mode
does not change project content or render settings.

## 4. Main-window regions

### 4.1 Menu bar

Required menu groups and initial actions:

- **File:** New, Open, Open Recent, Save, Save As, Close Project, Quit.
- **Edit:** Undo, Redo, Duplicate Layer, Delete Layer.
- **View:** Editor Mode, Preview Only, Full Screen, Layers, Inspector,
  Diagnostics, Reset Layout.
- **Playback:** Play/Pause, Step Generation, Reset, Jump to Time.
- **Render:** Validate Project, Render Video, Render Current Frame, Cancel
  Render when active.
- **Help:** Keyboard Shortcuts, About.

Undo/redo may arrive after the first editable milestone, but the UI and command
model must not make it difficult to add.

### 4.2 Toolbar

The default toolbar exposes New, Open, Save, the workspace-mode toggle, and the
primary Render Video action. It should not duplicate every menu command.

### 4.3 Layer pane

The layer pane replaces both the Explorer's fixed Layer A/Layer B controls and
the scene editor's MIDI channel entries.

Each row shows:

- Visibility/enabled checkbox.
- User-editable layer name.
- Compact `2D`, `3D`, or `W` type badge.
- Color/palette swatch where practical.
- Selection state and invalid-state indicator.

The list supports Add, Duplicate, Move Up, Move Down, and Delete. Drag/drop
reordering is desirable but not required for the first editable milestone.
The uppermost row is visually composited last. Reordering updates `z_index`
values deterministically.

The Add action presents `2D Automaton`, `3D Automaton`, and `Wolfram` choices
when their engines are available. Features that have not been implemented must
not appear as selectable controls.

### 4.4 Preview surface

The preview surface:

- Maintains the project output's 16:9 aspect ratio.
- Letterboxes rather than stretching.
- Renders internally at no more than 640×360 and 30 fps, independently of
  export resolution and fps.
- Shows the preview and export raster/fps separately in the HUD.
- Offers Fit, 50%, 100%, and 200% zoom choices.
- Uses nearest-neighbor display scaling by default for crisp cells.
- May offer smooth display scaling as a preview preference; this does not alter
  exported frames.
- Displays a neutral empty state when no valid project is loaded.
- Uses the same deterministic runtime and frame renderer as export.

The preview clock samples rational presentation time. For example, a 30 fps
preview of a 60 fps export skips every other export sample visually but reaches
the same automaton generation at the same timestamp. A `cell_size_px` grid is
always derived from export resolution, never preview resolution.

Editing directly on the grid is outside the first editor milestone. A later
cell-painting tool may be added without changing this layout.

### 4.5 Transport and HUD

The transport remains directly beneath the preview and contains:

- Jump to start/reset.
- Play/pause.
- Step one automaton generation.
- Reset.
- Current time and project duration.
- Optional time slider for deterministic restart-and-simulate scrubbing.

The compact HUD shows selected-layer generation, live-cell count, density,
logical grid size, and rule. Multi-layer projects may show aggregate status in
the strip and complete per-layer values in a popover or diagnostics pane.

### 4.6 Inspector

The inspector has two top-level tabs.

**Layer** operates on the selected layer and contains collapsible sections:

- **General:** name, enabled, dimension/type, order, Derived/Custom seed mode,
  and the resolved layer seed.
- **Simulation:** rule family, catalog rule or custom rule, neighborhood,
  boundary, and number of states.
- **Initial Condition:** initializer type, seed override, and
  initializer-specific values such as density, radius, cells, or RLE file.
- **Appearance:** 2D colors/gradient/trail/opacity or 3D palette/render
  style/coloring/voxel scale.
- **Timing:** step interval and visual fade settings.
- **Camera:** projection and motion settings for 3D layers only.

**Project** contains collapsible sections:

- **Project:** project name and master random seed.
- **Output:** resolution preset/custom size, fps, duration, codec quality, and
  destination.
- **Canvas:** background color and preview scaling preference.
- **Metadata:** schema and application versions shown read-only.

Fields that do not apply to the selected dimension, rule family, renderer, or
initializer are hidden rather than merely disabled. This carries forward the
reference editor's cascading forms while reducing visual noise.

### 4.7 Diagnostics and render progress

A collapsible bottom pane lists validation errors, warnings, and render logs.
Each validation item contains severity, affected field path, and an actionable
message. Selecting an error focuses the corresponding inspector field when
possible.

A normal render opens a non-modal render panel or dialog containing output
path, completed and total frames, percentage, elapsed time, estimated time
remaining, and Cancel. The main preview remains usable, but only one render job
can run at a time and the job uses the project snapshot captured at launch.

## 5. Control mapping

| Reference control | Native Qt control | Version 1 interpretation |
| --- | --- | --- |
| On | `QCheckBox` in layer row | Enable or disable layer |
| Stack / foreground / background | Layer list ordering | Numeric `z_index` |
| Dimension | `QComboBox` or Add Layer choice | 2D or 3D layer |
| Rule Type | `QComboBox` | Outer-totalistic or Wolfram |
| 2D/3D Rule | Categorized searchable `QComboBox` | Catalog rule key plus description |
| Wolfram Rule # | `QSpinBox` | Integer 0–255 |
| Palette | Categorized `QComboBox` with swatch | Catalog or custom palette |
| Color | Color button and native color dialog | 2D/custom base color |
| Opacity | Slider paired with `QDoubleSpinBox` | Layer alpha 0–1 |
| Grid / Grid Scale | Preset plus spin boxes | Explicit grid size or cell-derived size |
| Voxel | Preset plus `QDoubleSpinBox` | Automatic or fixed voxel scale |
| Fade | `QDoubleSpinBox` | Time-based visual fade |
| Order | Layer reordering controls | Normalized numeric `z_index` |
| Seed Radius | Initializer form | Radius for disc/sphere initializer |
| FG/BG Speed | Per-layer timing field | Step interval in seconds or generations/sec |
| Run / Step / Reset | `QToolButton` transport | Same deterministic behavior |
| HUD values | Labels under preview | Time, generation, population, density, grid, rule |
| JSON Preview | Read-only dialog | Normalized project JSON |
| Scene cards | Recent-project menu/dialog | Files rather than server-owned scenes |

Mutation, generations-per-event, event filters, channel type, target channel,
destroy controls, and collision controls have no native mapping.

## 6. Editing behavior

### 6.1 Change classes

Changes are divided into three classes so preview behavior is predictable:

- **Display-only changes** such as preview zoom do not alter project state or
  reset the simulation.
- **Render changes** such as color or opacity mark the project dirty and update
  the current frame without resetting cell state when safe.
- **Simulation changes** such as rule, boundary, grid, seed, or initializer mark
  the project dirty and reset the affected layer to frame zero.

If playback has advanced, the first simulation-changing edit in a sequence
pauses playback and shows a concise status message explaining the reset. It
must not open a confirmation dialog for every changed spin box value.

### 6.2 Update timing

- Text and numeric editors commit on editing-finished or after a short debounce,
  not on every partial keystroke.
- Color and opacity changes may update continuously when preview cost permits.
- Invalid partial input remains visibly invalid and does not replace the last
  valid runtime configuration.
- A project cannot render while blocking validation errors remain.

### 6.3 Dirty state and persistence

- The window title appends `*` while the project has unsaved changes.
- Save writes normalized JSON atomically through a temporary sibling file and
  replacement.
- New, Open, Close, and Quit prompt to Save, Discard, or Cancel when dirty.
- A project path is not inferred from the render destination.
- UI layout preferences are stored separately from project content.

## 7. Visual language and accessibility

The reference palette is the starting point, not a requirement to hard-code
web CSS values into widgets:

- Very dark neutral application and preview backgrounds.
- Slightly lighter panels with subtle borders.
- Teal primary accent for selection and primary actions.
- Green success, amber warning, and muted red error/destructive states.
- System UI font for forms; optional monospaced numerals in the HUD.

The Qt style sheet should use named application properties or centralized
constants. All essential state must be communicated by text or shape as well as
color. Controls require visible keyboard focus, usable tab order, tooltips for
specialized CA terminology, and labels that remain legible at common Linux
display scaling values.

## 8. Keyboard shortcuts

Initial shortcuts:

| Action | Shortcut |
| --- | --- |
| New project | `Ctrl+N` |
| Open project | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Play/pause | `Space` |
| Step generation | `Right` while preview has focus |
| Reset | `Ctrl+R` |
| Preview-only mode | `Tab` |
| Full screen | `F11` |
| Render video | `Ctrl+Shift+R` |
| Exit full screen | `Escape` |

Shortcuts must be suppressed when they conflict with active text editing.

## 9. Editable-UI milestones

The first milestone targeted the implemented 2D engine before the full version
1 feature set. It included:

1. The three-pane editor shell and preview-only mode.
2. A single-layer list with enable, select, and future-facing Add controls;
   duplicate/reorder become active once multiple layers are supported.
3. Project inspector fields for name, output resolution, fps, duration, and
   random seed.
4. Layer inspector fields for a general 2D outer-totalistic rule, grid size,
   boundary, initializer, live/dead colors, opacity, and step timing.
5. Catalog choices for all required 2D rules, including Generations rules.
6. Random, center block/disc, explicit-cell, and RLE initializers.
7. New, Open, Save, Save As, dirty-state handling, and atomic writes.
8. Live preview reset/update behavior as defined in section 6.
9. Existing background MP4 rendering integrated into the new layout.
10. UI and serialization tests for the complete edit-save-open-preview-render
    path.

Multi-layer composition, per-layer seed overrides, export-relative cell sizing,
and `wolfram_2d` have since been completed. The Wolfram inspector replaces
outer-totalistic rule controls with a rule-number field from 0 through 255 and
offers center-cell, seeded-random, and explicit-bit starting rows. The Add Layer
menu creates either an outer-totalistic 2D layer or a Wolfram 2D history layer.

3D, advanced gradients/trails, direct cell painting, and arbitrary timeline
scrubbing remain visible in the overall design but are not yet implemented.
Unimplemented controls must not be displayed as if they work.

### 9.1 Milestone acceptance

The milestone is complete when a user can launch the native application,
create a 2D project without editing JSON, choose a catalog or custom rule,
choose an initial condition, change its visual and output settings, preview it,
save it, reopen it without loss, and render a valid MP4. The layout must remain
usable at 1280×720 and preview-only mode must restore the previous editor layout
when exited.
