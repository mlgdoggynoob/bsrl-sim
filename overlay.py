"""Overlays for policy_video.py --overlay 1: what a battle frame holds, drawn over the game's own render.

    python -m overlay          # self-check (synthetic state, no host)

  boxes(view, pidx, cam, W, H)  -> [(cls, x0, y0, x1, y1)] image pixels: one box per entity the client renders (state2
                                   'client' flag), named with the showdown-vision det classes (bsrl brain/adapter.DET):
                                   player (the policy), enemy, enemy_summon, power_box, power_cube, teammate_projectile
                                   (the policy's own shots, as the det labels them), enemy_projectile. HUD and area
                                   classes are not drawn.
  path(walk, a, b)              -> [(tx, ty)] 8-neighbour A* over the walkable tiles from tile a to tile b (no corner
                                   cutting past a wall); [] when b cannot be reached
  ground(tiles, view?, cam, W, H) -> image pixels of tile centres at z = 0
  draw(img, boxes, line, text)  -> the RGB frame with the boxes (class tag above each), the path polyline and a text panel

Projection: engine/py/proj.py (the PC client's fitted battle camera, 2400 x 1080 full-res pixels, scaled to W x H), the
camera anchor from the host response (cam_x, cam_y), entity positions from the client object's rendered position when
the client has one (labels.entity_points does the same). Box sizes are world-unit extents per class (EXT), projected as
a cuboid and boxed in screen space."""
import heapq, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "engine", "py"))
import proj, state2 as S

TILE = 300
SIDE = 240                     # black side bars of the 2400 x 1080 screen, full-res px (engine/py/labels.HUD_BOXES_FULL)
# per class: (half width, height) of the cuboid in world units (1 tile = 300); eyeballed on rendered frames
EXT = {"player": (160, 520), "enemy": (160, 520), "enemy_summon": (150, 420), "power_box": (170, 380), "power_cube": (90, 160),
       "teammate_projectile": (70, 90), "enemy_projectile": (70, 90)}
COL = {"player": (0, 230, 255), "enemy": (255, 60, 60), "enemy_summon": (255, 140, 60), "power_box": (255, 220, 0),
       "power_cube": (220, 80, 255), "teammate_projectile": (120, 255, 255), "enemy_projectile": (255, 150, 0)}
_P = None


def params():
    global _P
    if _P is None: _P = proj.load_params()
    return _P


def _pos(r, xi, ci):
    """world (x, y, z) of a state2 row: the client's rendered position when it has one"""
    if r[ci] != S.NIL: return float(r[ci]), float(r[ci + 1]), max(0.0, float(r[ci + 2]))
    return float(r[xi]), float(r[xi + 1]), max(0.0, float(r[xi + 2]))


def box_of(cls, x, y, z, cam, W, H, P=None):
    """screen box (x0, y0, x1, y1) of a class cuboid standing at (x, y, z)"""
    P = P or params(); hw, h = EXT[cls]
    dx = np.array([-hw, hw, -hw, hw] * 2, np.float64); dy = np.array([-hw, -hw, hw, hw] * 2, np.float64)
    dz = np.array([0.0] * 4 + [h] * 4)
    u, v = proj.project(x + dx, y + dy, z + dz, cam, P)
    sx, sy = W / proj.FULL[0], H / proj.FULL[1]
    return float(u.min() * sx), float(v.min() * sy), float(u.max() * sx), float(v.max() * sy)


def boxes(view, pidx, cam, W, H, P=None):
    """[(cls, x0, y0, x1, y1)] of every rendered entity of a state2.StateView, from player pidx's side"""
    s = view.s; ch = s["chars"]; out = []
    me = view.player_char(pidx); my_team = None
    if me is not None:
        pl = s["players"]; t = pl[pl[:, 0] == pidx]; my_team = int(t[0, 1]) if len(t) else None
    team_of = {int(p[0]): int(p[1]) for p in s["players"]}
    for i in range(len(ch)):
        r = ch[i]
        if r[18] != 0 or r[6] <= 0 or r[19] != 1: continue
        if view.box[i]: cls = "power_box"
        elif view.brawler[i]: cls = "player" if int(r[2]) == pidx else "enemy"
        elif view.summon[i]:
            if team_of.get(int(r[2])) == my_team and my_team is not None: continue   # own summons: no class in solo
            cls = "enemy_summon"
        else: continue
        out.append((cls,) + box_of(cls, *_pos(r, 3, 20), cam, W, H, P))
    for r in s["proj"]:
        if r[14] != 1 or r[12] == 1: continue
        cls = "teammate_projectile" if int(r[2]) == pidx else "enemy_projectile"
        out.append((cls,) + box_of(cls, *_pos(r, 3, 15), cam, W, H, P))
    for r in s["items"]:
        if r[8] != 1 or r[1] != S.CUBE_ITEM: continue
        x, y, _ = _pos(r, 3, 9)                     # items at their ground point (labels.entity_points)
        out.append(("power_cube",) + box_of("power_cube", x, y, 0.0, cam, W, H, P))
    x0, x1 = SIDE * W / proj.FULL[0], (proj.FULL[0] - SIDE) * W / proj.FULL[0]   # the world is drawn between the side bars
    return [(c, max(u0, x0), v0, min(u1, x1), v1) for c, u0, v0, u1, v1 in out if u1 > x0 and u0 < x1 and v1 > 0 and v0 < H]


def path(walk, a, b):
    """8-neighbour A* on walk (H, W) bool from tile a = (tx, ty) to b; diagonals only when both side tiles are walkable"""
    Hh, Ww = walk.shape; a = (int(a[0]), int(a[1])); b = (int(b[0]), int(b[1]))
    ok = lambda t: 0 <= t[0] < Ww and 0 <= t[1] < Hh and bool(walk[t[1], t[0]])
    if not ok(b): return []
    if not ok(a) and a != b: pass                  # start tile may be a bush edge / spawn: search from it anyway
    hfn = lambda t: max(abs(t[0] - b[0]), abs(t[1] - b[1])) + 0.414 * min(abs(t[0] - b[0]), abs(t[1] - b[1]))
    g = {a: 0.0}; prev = {}; q = [(hfn(a), a)]
    while q:
        _, t = heapq.heappop(q)
        if t == b:
            out = [t]
            while t in prev: t = prev[t]; out.append(t)
            return out[::-1]
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                if not ddx and not ddy: continue
                n = (t[0] + ddx, t[1] + ddy)
                if not ok(n): continue
                if ddx and ddy and not (ok((t[0] + ddx, t[1])) and ok((t[0], t[1] + ddy))): continue
                c = g[t] + (1.414 if ddx and ddy else 1.0)
                if c < g.get(n, np.inf):
                    g[n] = c; prev[n] = t; heapq.heappush(q, (c + hfn(n), n))
    return []


def ground(tiles, cam, W, H, P=None):
    """[(u, v)] image pixels of tile centres on the ground"""
    if not tiles: return []
    P = P or params(); t = np.asarray(tiles, np.float64)
    u, v = proj.project((t[:, 0] + 0.5) * TILE, (t[:, 1] + 0.5) * TILE, np.zeros(len(t)), cam, P)
    return list(zip((u * W / proj.FULL[0]).tolist(), (v * H / proj.FULL[1]).tolist()))


_FONT = {}


def font(size):
    from PIL import ImageFont
    if size not in _FONT:
        try: _FONT[size] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except OSError: _FONT[size] = ImageFont.load_default()
    return _FONT[size]


def draw(img, bxs, line=(), text=(), target=None):
    """img (H, W, 3) uint8 -> the same frame with the overlays (a new array)"""
    from PIL import Image, ImageDraw
    im = Image.fromarray(np.ascontiguousarray(img)); d = ImageDraw.Draw(im); H = im.size[1]; lw = max(2, H // 300)
    if len(line) >= 2: d.line([tuple(p) for p in line], fill=(255, 255, 255), width=lw + 2, joint="curve")
    if target is not None:
        r = H // 60; d.ellipse([target[0] - r, target[1] - r, target[0] + r, target[1] + r], outline=(255, 255, 255), width=lw + 1)
    f = font(max(12, H // 48))
    for cls, x0, y0, x1, y1 in bxs:
        c = COL[cls]; d.rectangle([x0, y0, x1, y1], outline=c, width=lw)
        tw = d.textlength(cls, font=f); th = f.size + 4
        d.rectangle([x0, y0 - th, x0 + tw + 6, y0], fill=c); d.text((x0 + 3, y0 - th + 1), cls, fill=(0, 0, 0), font=f)
    if text:
        f2 = font(max(14, H // 40)); y = 10
        wmax = max(d.textlength(t, font=f2) for t in text)
        d.rectangle([8, 6, 22 + wmax, 14 + len(text) * (f2.size + 6)], fill=(0, 0, 0))
        for t in text: d.text((15, y), t, fill=(255, 255, 255), font=f2); y += f2.size + 6
    return np.asarray(im)


def _check():
    # path: around a wall, no corner cutting
    walk = np.ones((6, 6), bool); walk[1:5, 2] = False
    p = path(walk, (0, 2), (4, 2))
    assert p[0] == (0, 2) and p[-1] == (4, 2) and all(walk[y, x] for x, y in p), p
    assert all(max(abs(p[i + 1][0] - p[i][0]), abs(p[i + 1][1] - p[i][1])) == 1 for i in range(len(p) - 1))
    for (x0, y0), (x1, y1) in zip(p, p[1:]):
        if x0 != x1 and y0 != y1: assert walk[y0, x1] and walk[y1, x0], p
    walk2 = walk.copy(); walk2[:, 2] = False
    assert path(walk2, (0, 2), (4, 2)) == [] and path(walk, (0, 0), (2, 2)) == []
    # projection: a box above the anchor sits on screen, taller boxes reach higher, nearer (lower) rows sit lower
    P = {"u0": 1200.0, "v0": 455.0, "Fx": 3150.0, "Fy": 2800.0, "F": 2800.0, "D": 12850.0, "th": 0.47, "ox": 0.0, "oy": 0.0}
    cam = (0.16 * 3000, 0.12 * 3000)
    b = box_of("player", 3000, 3000, 0, cam, 1920, 864, P); c = box_of("power_cube", 3000, 3000, 0, cam, 1920, 864, P)
    assert 0 < b[0] < b[2] < 1920 and 0 < b[1] < b[3] < 864 and b[1] < c[1] and abs(b[3] - c[3]) < 15, (b, c)
    lo = box_of("player", 3000, 3600, 0, cam, 1920, 864, P); assert lo[3] > b[3], (lo, b)
    # boxes(): a synthetic dump: me, an enemy, a box, my shot, its shot, a cube; one char not rendered
    NIL = S.NIL
    pl = np.array([[0, 0, 100, NIL, 0, 0, 1, 0], [1, 1, 101, NIL, 0, 0, 1, 1]], np.int32)
    def ch(cid, did, own, x, y, client=1): return [cid, did, own, x, y, 0, 1000, 1000] + [0] * 10 + [0, client, NIL, NIL, NIL]
    chars = np.array([ch(100, S.SNIPER, 0, 3000, 3000), ch(101, S.SNIPER, 1, 3600, 3000), ch(5, 16000120, -1, 3000, 3600),
                      ch(102, S.SNIPER, 1, 9000, 9000, client=0)], np.int32)
    def pj(own): return [7, 6000001, own, 3100, 3000, 100, 0, 0, 0, 0, 0, 0, 0, 0, 1, NIL, NIL, NIL]
    projs = np.array([pj(0), pj(1)], np.int32)
    items = np.array([[9, S.CUBE_ITEM, -1, 2700, 3000, 0, 0, 1, 1, NIL, NIL, NIL]], np.int32)
    hdr = np.array([S.MAGIC, 0, 50, 2, len(chars), 2, 1, 0], np.int32)
    buf = np.concatenate([hdr, pl.ravel(), chars.ravel(), projs.ravel(), items.ravel()]); buf[1] = len(buf)
    global _P; _P = P
    v = S.StateView(buf.astype("<i4").tobytes(), {}, None)
    got = sorted(c for c, *_ in boxes(v, 0, cam, 1920, 864, P))
    assert got == sorted(["player", "enemy", "power_box", "teammate_projectile", "enemy_projectile", "power_cube"]), got
    img = draw(np.zeros((864, 1920, 3), np.uint8), boxes(v, 0, cam, 1920, 864, P), ground(p, cam, 1920, 864, P),
               ["planner (display only): farm", "cube 3 tiles S: picking up"])
    assert img.shape == (864, 1920, 3) and img.any()
    print("overlay check ok (%d boxes, path %d tiles)" % (len(got), len(p)))


if __name__ == "__main__":
    _check()
