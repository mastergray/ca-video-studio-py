#!/usr/bin/env python3
"""
ca_video.py — render 2D or 3D cellular automata to MP4 from a JSON config.

Usage:
    python ca_video.py config.json [-o out.mp4]

Requires: numpy, imageio, imageio-ffmpeg  (pip install numpy imageio imageio-ffmpeg)

Model
-----
Outer-totalistic "Generations" automata (Life-like rules are the 2-state case):
  * state 0 = dead, state 1 = alive, states 2..N-1 = dying (decay one step per tick,
    don't count as neighbors, can't be reborn until they reach 0).
  * A dead cell with a live-neighbor count in `birth` becomes alive.
  * A live cell with a count in `survive` stays alive; otherwise it starts dying
    (or dies outright when states == 2).
"""
import argparse
import json
import math
import sys

import numpy as np
import imageio.v2 as imageio


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

DEFAULTS = {
    "dimensions": 2,
    "size": None,                 # [w, h] or [x, y, z]
    "rule": None,                 # e.g. "B3/S23" (or give birth/survive lists)
    "birth": None,
    "survive": None,
    "states": 2,
    "neighborhood": "moore",      # "moore" | "von_neumann"
    "wrap": True,
    "seed": None,
    "steps": 300,
    "init": {"type": "random", "density": 0.3},
    "video": {
        "output": "out.mp4",
        "fps": 30,
        "width": 720,
        "height": 720,
        "steps_per_frame": 1,
        "hold_start_frames": 0,
        "hold_end_frames": 15,
        "quality": 8,
    },
    "colors": {
        "background": "#0b0d12",
        "gradient": ["#ffffff", "#3aa0ff", "#1b2a55"],  # alive → … → last dying state
        "trail": 0.0,             # 2D only: 0 = off, 0..1 = fade factor of dead cells
        "trail_color": "#233a6b",
        "color_by": "state",      # 3D: "state" | "height" | "distance"
    },
    "camera": {                   # 3D only
        "elevation": 28,
        "azimuth": 30,
        "rotate_deg_per_frame": 0.6,
        "zoom": 1.0,
        "perspective": 0.35,      # 0 = orthographic
        "voxel_scale": 0.92,      # voxel size relative to cell spacing
    },
}


def deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def parse_counts(spec):
    """'23' -> {2,3}; '4-6,9' -> {4,5,6,9}; [2, 3, "5-7"] -> {2,3,5,6,7}."""
    if spec is None:
        return set()
    if isinstance(spec, int):
        return {spec}
    if isinstance(spec, list):
        out = set()
        for s in spec:
            out |= parse_counts(s)
        return out
    spec = str(spec).strip()
    if not spec:
        return set()
    if "," not in spec and "-" not in spec:
        return {int(c) for c in spec}          # classic single-digit form
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out |= set(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def parse_rule(cfg):
    birth, survive, states = cfg.get("birth"), cfg.get("survive"), cfg["states"]
    rule = cfg.get("rule")
    if rule:
        for part in str(rule).upper().split("/"):
            part = part.strip()
            if part.startswith("B"):
                birth = part[1:]
            elif part.startswith("S"):
                survive = part[1:]
            elif part.startswith("C") or part.startswith("G"):
                states = int(part[1:])
    b, s = parse_counts(birth), parse_counts(survive)
    if not b and not s:
        sys.exit("Config needs a rule, e.g. \"rule\": \"B3/S23\", or birth/survive lists.")
    return b, s, max(2, int(states))


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def gradient_colors(stops, n):
    """Interpolate n colors along a list of hex stops."""
    stops = [hex_to_rgb(c) for c in stops]
    if n == 1 or len(stops) == 1:
        return np.array([stops[0]] * n)
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        j = min(int(t), len(stops) - 2)
        f = t - j
        out.append(stops[j] * (1 - f) + stops[j + 1] * f)
    return np.array(out)


# ----------------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------------

def neighbor_offsets(dims, kind):
    offs = []
    for d in np.ndindex(*([3] * dims)):
        o = tuple(x - 1 for x in d)
        if all(v == 0 for v in o):
            continue
        if kind == "von_neumann" and sum(abs(v) for v in o) != 1:
            continue
        offs.append(o)
    return offs


class Automaton:
    def __init__(self, cfg):
        self.dims = int(cfg["dimensions"])
        if self.dims not in (2, 3):
            sys.exit("dimensions must be 2 or 3")
        size = cfg["size"] or ([128, 128] if self.dims == 2 else [48, 48, 48])
        if len(size) != self.dims:
            sys.exit(f"size must have {self.dims} entries")
        # store grid as [z][y][x] / [y][x]
        self.shape = tuple(int(s) for s in reversed(size))
        self.birth, self.survive, self.states = parse_rule(cfg)
        self.wrap = bool(cfg["wrap"])
        self.offsets = neighbor_offsets(self.dims, cfg["neighborhood"])
        self.rng = np.random.default_rng(cfg.get("seed"))
        self.grid = np.zeros(self.shape, dtype=np.uint8)
        self._init(cfg["init"])
        maxn = len(self.offsets)
        self.birth_lut = np.zeros(maxn + 1, bool)
        self.surv_lut = np.zeros(maxn + 1, bool)
        for c in self.birth:
            if c <= maxn:
                self.birth_lut[c] = True
        for c in self.survive:
            if c <= maxn:
                self.surv_lut[c] = True

    # -- initial conditions ---------------------------------------------------
    def _init(self, init):
        kind = init.get("type", "random")
        density = float(init.get("density", 0.3))
        if kind == "random":
            self.grid[:] = self.rng.random(self.shape) < density
        elif kind in ("center", "center_block", "center_cube"):
            r = int(init.get("radius", max(2, min(self.shape) // 8)))
            sl = tuple(slice(max(0, s // 2 - r), s // 2 + r) for s in self.shape)
            block = self.rng.random(self.grid[sl].shape) < density
            self.grid[sl] = block
        elif kind == "sphere":
            r = float(init.get("radius", min(self.shape) / 4))
            idx = np.indices(self.shape)
            c = [(s - 1) / 2 for s in self.shape]
            dist = np.sqrt(sum((idx[i] - c[i]) ** 2 for i in range(self.dims)))
            self.grid[:] = (dist <= r) & (self.rng.random(self.shape) < density)
        elif kind == "cells":
            # list of [x, y] or [x, y, z]; "offset": "center" to center the pattern
            cells = np.array(init["cells"], dtype=int)
            if init.get("offset", "center") == "center":
                span = cells.max(0) - cells.min(0)
                start = np.array(list(reversed(self.shape))) // 2 - span // 2
                cells = cells - cells.min(0) + start
            for c in cells:
                self.grid[tuple(reversed(c.tolist()))] = 1
        elif kind == "rle":
            self._load_rle(init["pattern"])
        else:
            sys.exit(f"Unknown init type: {kind}")

    def _load_rle(self, rle):
        if self.dims != 2:
            sys.exit("RLE patterns are 2D only")
        body = "".join(l for l in rle.splitlines()
                       if l.strip() and not l.startswith(("#", "x")))
        rows, row, num = [], [], ""
        for ch in body:
            if ch.isdigit():
                num += ch
            elif ch in "bo.A":
                row += [0 if ch in "b." else 1] * int(num or 1); num = ""
            elif ch == "$":
                rows.append(row); rows += [[]] * (int(num or 1) - 1); row, num = [], ""
            elif ch == "!":
                break
        rows.append(row)
        w = max(len(r) for r in rows)
        pat = np.array([r + [0] * (w - len(r)) for r in rows], dtype=np.uint8)
        H, W = self.shape
        y0, x0 = (H - pat.shape[0]) // 2, (W - pat.shape[1]) // 2
        self.grid[y0:y0 + pat.shape[0], x0:x0 + pat.shape[1]] = pat

    # -- step -------------------------------------------------------------------
    def _count(self, alive):
        a = alive.astype(np.uint8)
        if self.wrap:
            n = np.zeros(self.shape, np.uint8)
            for o in self.offsets:
                n += np.roll(a, o, axis=tuple(range(self.dims)))
            return n
        p = np.pad(a, 1)
        n = np.zeros(self.shape, np.uint8)
        for o in self.offsets:
            sl = tuple(slice(1 + d, 1 + d + s) for d, s in zip(o, self.shape))
            n += p[sl]
        return n

    def step(self):
        g = self.grid
        alive = g == 1
        n = self._count(alive)
        born = (g == 0) & self.birth_lut[n]
        stay = alive & self.surv_lut[n]
        new = np.zeros_like(g)
        if self.states > 2:
            decaying = (g > 1) | (alive & ~stay)
            new[decaying] = g[decaying] + 1
            new[new >= self.states] = 0
        new[born | stay] = 1
        self.grid = new


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

def even16(v):
    return max(16, int(round(v / 16)) * 16)


class Renderer2D:
    def __init__(self, cfg, ca):
        v, c = cfg["video"], cfg["colors"]
        self.W, self.H = even16(v["width"]), even16(v["height"])
        self.bg = hex_to_rgb(c["background"])
        self.palette = np.vstack([self.bg[None], gradient_colors(c["gradient"], ca.states - 1)])
        self.trail = float(c.get("trail", 0))
        self.trail_rgb = hex_to_rgb(c.get("trail_color", "#233a6b"))
        self.buf = np.zeros(ca.shape, np.float32)
        gh, gw = ca.shape
        self.scale = max(1, min(self.W // gw, self.H // gh))
        self.ox = (self.W - gw * self.scale) // 2
        self.oy = (self.H - gh * self.scale) // 2

    def render(self, grid):
        img = self.palette[grid]
        if self.trail > 0:
            self.buf = np.maximum(self.buf * self.trail, (grid == 1).astype(np.float32))
            ghost = (grid == 0)[..., None] * self.buf[..., None]
            img = img * (1 - ghost) + (self.bg + (self.trail_rgb - self.bg)) * ghost
        img = np.repeat(np.repeat(img, self.scale, 0), self.scale, 1)
        frame = np.empty((self.H, self.W, 3), np.float32)
        frame[:] = self.bg
        frame[self.oy:self.oy + img.shape[0], self.ox:self.ox + img.shape[1]] = img
        return frame.clip(0, 255).astype(np.uint8)


class Renderer3D:
    """Numpy voxel splatter: rotate, project, z-buffer shaded squares."""

    def __init__(self, cfg, ca):
        v, c, cam = cfg["video"], cfg["colors"], cfg["camera"]
        self.W, self.H = even16(v["width"]), even16(v["height"])
        self.bg = hex_to_rgb(c["background"])
        self.color_by = c.get("color_by", "state")
        self.grad = c["gradient"]
        self.state_cols = gradient_colors(self.grad, ca.states - 1)
        self.lut = gradient_colors(self.grad, 256)
        self.cam = cam
        self.shape = ca.shape                            # (z, y, x)
        self.center = (np.array(self.shape[::-1], np.float32) - 1) / 2
        self.radius = float(np.linalg.norm(np.array(self.shape, np.float32)) / 2)
        self.base_px = min(self.W, self.H) * 0.46 * cam.get("zoom", 1.0) / self.radius
        self.frame_idx = 0
        # background vignette, computed once
        yy, xx = np.mgrid[0:self.H, 0:self.W]
        d = np.sqrt(((xx - self.W / 2) / self.W) ** 2 + ((yy - self.H / 2) / self.H) ** 2)
        self.bg_img = (self.bg * (1.15 - 0.5 * d)[..., None]).astype(np.float32)

    def render(self, grid):
        cam = self.cam
        az = math.radians(cam.get("azimuth", 30) + cam.get("rotate_deg_per_frame", 0) * self.frame_idx)
        el = math.radians(cam.get("elevation", 28))
        self.frame_idx += 1
        frame = self.bg_img.copy()

        zz, yy, xx = np.nonzero(grid)
        if len(xx) == 0:
            return frame.clip(0, 255).astype(np.uint8)
        states = grid[zz, yy, xx]
        # world coords: x right, y depth, z up (grid z axis is "up")
        p = np.stack([xx, yy, zz], 1).astype(np.float32) - self.center

        # colors
        if self.color_by == "height":
            t = (zz / max(1, self.shape[0] - 1) * 255).astype(int)
            col = self.lut[255 - t]
        elif self.color_by == "distance":
            t = np.linalg.norm(p, axis=1) / self.radius
            col = self.lut[(t.clip(0, 1) * 255).astype(int)]
        else:
            col = self.state_cols[states - 1]

        # rotate: azimuth around z, then tilt by elevation
        ca_, sa = math.cos(az), math.sin(az)
        x1 = p[:, 0] * ca_ - p[:, 1] * sa
        y1 = p[:, 0] * sa + p[:, 1] * ca_
        z1 = p[:, 2]
        ce, se = math.cos(el), math.sin(el)
        depth = y1 * ce + z1 * se            # larger = farther from camera
        up = -y1 * se + z1 * ce

        persp = cam.get("perspective", 0.35)
        f = 1.0 / (1.0 + persp * depth / (self.radius * 2)) if persp else np.ones_like(depth)
        sx = self.W / 2 + x1 * self.base_px * f
        sy = self.H / 2 - up * self.base_px * f
        size = np.maximum(1, np.round(self.base_px * f * cam.get("voxel_scale", 0.92))).astype(int)

        # depth shading (near = bright) + simple light from top-left per sprite
        dn = (depth - depth.min()) / max(1e-6, np.ptp(depth))
        shade = 1.05 - 0.55 * dn

        smax = int(size.max())
        half = size // 2
        x0 = np.round(sx).astype(int) - half
        y0 = np.round(sy).astype(int) - half

        pix_list, dep_list, rgb_list = [], [], []
        for oy in range(smax):
            for ox in range(smax):
                m = (ox < size) & (oy < size)
                if not m.any():
                    continue
                px, py = x0[m] + ox, y0[m] + oy
                inb = (px >= 0) & (px < self.W) & (py >= 0) & (py < self.H)
                if not inb.any():
                    continue
                s = size[m][inb]
                # bevel: lighter top/left edge, darker bottom/right edge
                edge = np.ones(len(s), np.float32)
                if smax >= 4:
                    edge[(ox == 0) | (oy == 0)] = 1.18
                    edge[(ox == s - 1) | (oy == s - 1)] = 0.62
                    grad = 1.08 - 0.16 * (ox + oy) / np.maximum(1, 2 * (s - 1))
                    edge *= grad
                pix_list.append(py[inb] * self.W + px[inb])
                dep_list.append(depth[m][inb])
                rgb_list.append(col[m][inb] * (shade[m][inb] * edge)[:, None])

        pix = np.concatenate(pix_list)
        dep = np.concatenate(dep_list)
        rgb = np.concatenate(rgb_list)
        order = np.argsort(dep, kind="stable")          # nearest first
        pix, rgb = pix[order], rgb[order]
        _, first = np.unique(pix, return_index=True)    # nearest per pixel wins
        flat = frame.reshape(-1, 3)
        flat[pix[first]] = rgb[first]
        return frame.clip(0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def run(cfg, out_override=None):
    cfg = deep_merge(DEFAULTS, cfg)
    v = cfg["video"]
    out = out_override or v["output"]
    ca = Automaton(cfg)
    renderer = Renderer2D(cfg, ca) if ca.dims == 2 else Renderer3D(cfg, ca)

    steps, spf = int(cfg["steps"]), max(1, int(v["steps_per_frame"]))
    n_frames = steps // spf
    writer = imageio.get_writer(out, fps=v["fps"], codec="libx264",
                                quality=v.get("quality", 8), pixelformat="yuv420p",
                                macro_block_size=16)
    try:
        frame = renderer.render(ca.grid)
        for _ in range(int(v.get("hold_start_frames", 0)) + 1):
            writer.append_data(frame)
        for i in range(n_frames):
            for _ in range(spf):
                ca.step()
            frame = renderer.render(ca.grid)
            writer.append_data(frame)
            if (i + 1) % 25 == 0 or i + 1 == n_frames:
                live = int((ca.grid == 1).sum())
                print(f"\rframe {i + 1}/{n_frames}  live cells: {live}   ", end="", flush=True)
        hold = int(v.get("hold_end_frames", 0))
        for _ in range(hold):
            if ca.dims == 3 and cfg["camera"].get("rotate_deg_per_frame", 0):
                frame = renderer.render(ca.grid)   # keep the camera turning
            writer.append_data(frame)
    finally:
        writer.close()
    print(f"\nwrote {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Cellular automaton → MP4")
    ap.add_argument("config", help="path to JSON config")
    ap.add_argument("-o", "--output", help="override output path")
    args = ap.parse_args()
    with open(args.config) as fh:
        cfg = json.load(fh)
    run(cfg, args.output)


if __name__ == "__main__":
    main()
