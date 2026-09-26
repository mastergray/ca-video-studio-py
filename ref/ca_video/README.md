# ca_video — cellular automata → MP4

```
pip install numpy imageio imageio-ffmpeg
python ca_video.py examples/life_2d.json            # writes the "output" path
python ca_video.py examples/crystal_3d.json -o x.mp4
```

## Config reference (all keys optional except the rule)

| Key | Meaning | Default |
|---|---|---|
| `dimensions` | `2` or `3` | `2` |
| `size` | `[w, h]` or `[x, y, z]` | `[128,128]` / `[48,48,48]` |
| `rule` | `"B3/S23"`, `"B2/S/C3"`, `"B4/S4-5/C5"` — B = birth counts, S = survive counts, C = number of states. Use commas/ranges for counts ≥ 10 (`"B5-7,12/S1-3,26"`) | — |
| `birth`, `survive` | alternative to `rule`: lists like `[3]`, `[2, 3, "5-7"]` | — |
| `states` | ≥ 2; extra states are decay ("Generations") | `2` |
| `neighborhood` | `"moore"` (8 / 26) or `"von_neumann"` (4 / 6) | `"moore"` |
| `wrap` | toroidal edges | `true` |
| `seed` | RNG seed for reproducible runs | random |
| `steps` | simulation steps | `300` |
| `init` | see below | random 30% |
| `video` | `output`, `fps`, `width`, `height` (rounded to ×16), `steps_per_frame`, `hold_start_frames`, `hold_end_frames`, `quality` (0–10) | |
| `colors` | `background`, `gradient` (hex stops: alive → last decay state), `trail` (2D ghosting 0–1), `trail_color`, `color_by` (3D: `state` / `height` / `distance`) | |
| `camera` (3D) | `elevation`, `azimuth`, `rotate_deg_per_frame`, `zoom`, `perspective` (0 = ortho), `voxel_scale` | |

### `init` types
- `{"type": "random", "density": 0.3}`
- `{"type": "center", "radius": 10, "density": 0.5}` — random block/cube in the middle
- `{"type": "sphere", "radius": 12, "density": 0.4}`
- `{"type": "cells", "cells": [[1,0],[2,1],[0,2],[1,2],[2,2]]}` — explicit coords, centered
- `{"type": "rle", "pattern": "bo$2bo$3o!"}` — Golly/LifeWiki RLE (2D)

## Rules worth trying
- 2D: `B3/S23` Life · `B36/S23` HighLife · `B2/S/C3` Brian's Brain · `B3678/S34678` Day & Night · `B1357/S1357` Replicator
- 3D: `B4/S4-5/C5` crystal growth (small center seed, `wrap: false`) · `B4/S4/C5` "445" · `B13-14,17-19/S13-26/C2` "Clouds" (random 50%)
