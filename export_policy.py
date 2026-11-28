"""Checkpoint -> ONNX policy for the BSRL bot (its brain/policy.py loads it; contract in its dev/docs/MODELS.md).

    python -m export_policy CKPT OUT.onnx --trained Sniper[,Gunslinger...] [--name run/uN] [--team 1] [--ticks 2]
    python -m export_policy --check      # self-check: a fresh Policy through the export (CPU, no host)

Graph = Policy.forward on one decision (B = 1):
    inputs  (batch axis dynamic; the bot runs B = 1) s (1, N_S) float32 = cat[self (8), cond (37), intent (13)], ent (1, N_ENT, F_ENT) float32,
            grid (1, G, G) uint8, h (1, HID) float32
    outputs move (1, 17), fire (1, 5) (obs_v5.FIRE; super / gadget / hypercharge masked to -1e9 in the graph while self
            2 / 3 / 4 is off),
            aim (1, 360) log-probs, dist (1, 8), h_out (1, HID)
Metadata `spec` (JSON): obs_version, the shapes (n_self, n_cond, n_int, n_ent, f_ent, g, hid), fire classes, ticks,
team_size, gadgets (trained with --gadgets: the bot may set self 3 from
the gadget button; else it keeps it 0 as in training), hyper (trained with --hyper: the bot may set self 4 when the
hypercharge can be activated; else 0; obs v5.8: self 4 is no longer "the hypercharge bar is full"), sliders + presets (cond order), trained (characters.csv ItemName, lower case = the bot's brawler names),
heroes {item name: {name, display, stats (13), speed (tiles / tick), cls (7, v5.11)}} for every brawler identity can name (obs_v5.id_lut:
the enemy / teammate rows' identity columns live, the countdown name reader's closed set of display names), ckpt.
OUT.ref.npz: 64 random decisions through torch (the bot's test replays them through onnxruntime, atol 1e-4).
--trained takes characters.csv names (Sniper) or item names (piper); the bot plays only those brawlers on the policy."""
import argparse, json, os, sys
import numpy as np
import torch
import obs_v5 as O
import model as Mo

OUTS = ("move", "fire", "aim", "dist", "h_out")


@torch.no_grad()
def hero_table():
    """{item name: {name, display, stats, speed}} for obs_v5.hero_names (id_lut order); display = texts.csv EN (upper
    case on the countdown / brawler cards), speed = characters.csv Speed (units / s) -> tiles per 50 ms tick"""
    from nbpc import diversity as D
    t, tx = D.table("characters.csv"), _texts()
    names, lut = O.id_lut(); out = {}
    for k, n in enumerate(names):
        r = t[n][1]; item = (r.get("ItemName") or n).strip().lower()
        out[item] = {"name": n, "display": tx.get(r.get("TID") or "", item.upper()), "row": k,
                     "stats": [round(float(v), 6) for v in lut[k]], "speed": float(r.get("Speed") or 0) / 20 / 300,
                     "cls": [float(v) for v in O.cls_lut()[k]]}   # v5.11: the class one-hot (obs_v5.CLASSES) the bot writes
    return out


def _texts():
    """texts.csv TID -> EN (the game's localisation table, next to csv_logic in the APK assets)"""
    import csv
    from nbpc import diversity as D
    p = os.path.join(D.ASSETS, "localization", "texts.csv")
    if not os.path.exists(p): return {}
    with open(p, encoding="utf-8", newline="") as f:
        return {r[0]: r[1] for r in list(csv.reader(f))[2:] if len(r) > 1}


def resolve_trained(names, table):
    """characters.csv names or item names -> item names (lower case); unknown names fail loudly"""
    by_name = {v["name"].lower(): k for k, v in table.items()}
    out = []
    for n in (x.strip().lower() for x in names if x.strip()):
        k = n if n in table else by_name.get(n)
        assert k, f"--trained {n!r}: not a brawler identity can name (obs_v5.hero_names)"
        out.append(k)
    return out


def spec(net_name, trained, table, team=1, ticks=2, gadgets=False, hyper=False):
    return {"obs_version": O.OBS_VERSION, "gadgets": bool(gadgets), "hyper": bool(hyper), "n_self": O.N_SELF, "n_cond": O.N_COND, "n_int": O.N_INT, "n_s": O.N_S,
            "n_ent": O.N_ENT, "f_ent": O.F_ENT, "g": O.G, "hid": Mo.HID, "fire": list(O.FIRE), "intents": list(O.INTENTS), "ticks": ticks,
            "team_size": team, "sliders": list(O.SLIDERS), "presets": {k: O.preset_vec(k).tolist() for k in O.PRESETS},
            "trained": trained, "heroes": table, "ckpt": net_name}


class _One(torch.nn.Module):
    def __init__(self, net): super().__init__(); self.net = net

    def forward(self, s, ent, grid, h):
        (mv, fi, ai, di), _, h = self.net(s, ent, grid, h)
        return mv, fi, ai, di, h


def sample_inputs(n, seed=0):
    """n random single decisions in the observation's ranges (super / gadget / hypercharge ready flags both ways)"""
    g = torch.Generator().manual_seed(seed)
    s = torch.rand(n, O.N_S, generator=g); s[:, 2] = (s[:, 2] > 0.5).float(); s[:, 3] = (s[:, 3] > 0.5).float(); s[:, 4] = (s[:, 4] > 0.5).float()
    ent = torch.zeros(n, O.N_ENT, O.F_ENT); here = torch.rand(n, O.N_ENT, generator=g) < 0.4
    cls = torch.randint(len(O.ENT), (n, O.N_ENT), generator=g)
    ent[..., 0] = here.float(); ent.scatter_(2, (1 + cls)[..., None], here[..., None].float())
    ent[..., O.XY:O.XY + 2] = (torch.rand(n, O.N_ENT, 2, generator=g) - 0.5) * 2 * here[..., None]
    ent[..., O.VEL:O.F_ENT] = torch.rand(n, O.N_ENT, O.F_ENT - O.VEL, generator=g) * 0.3 * here[..., None]
    grid = torch.randint(O.UNKNOWN + 1, (n, O.G, O.G), generator=g, dtype=torch.uint8)
    h = torch.randn(n, Mo.HID, generator=g) * 0.3
    return s, ent, grid, h


@torch.no_grad()
def export(net, out, sp, n_ref=64):
    import onnx
    net = net.eval(); one = _One(net)
    x = sample_inputs(1)
    r2d, at2 = torch.rad2deg, torch.atan2   # while tracing: no ONNX symbolic for rad2deg (the same multiply), and the
    torch.rad2deg = lambda t: t * (180.0 / np.pi)   # exported atan2 divides by x: NaN at (0, 0) (empty rows), torch 0
    torch.atan2 = lambda y, x: at2(y, torch.where((x == 0) & (y == 0), torch.ones_like(x), x))
    try:
        torch.onnx.export(one, x, out, input_names=["s", "ent", "grid", "h"], output_names=list(OUTS), opset_version=17,
                          dynamo=False, dynamic_axes={k: {0: "b"} for k in ("s", "ent", "grid", "h") + OUTS})
    finally:
        torch.rad2deg, torch.atan2 = r2d, at2
    m = onnx.load(out); m.metadata_props.add(key="spec", value=json.dumps(sp)); onnx.save(m, out)
    xs = sample_inputs(n_ref, seed=1); ref = {k: v.numpy() for k, v in zip(("s", "ent", "grid", "h"), xs)}
    rows = [one(*(t[i:i + 1] for t in xs)) for i in range(n_ref)]
    for j, k in enumerate(OUTS): ref[k] = torch.cat([r[j] for r in rows]).numpy()
    np.savez(out[:-len(".onnx")] + ".ref.npz", **ref)
    return ref


def check_onnx(path, ref):
    """the exported graph on onnxruntime CPU vs the torch rows (one decision at a time, as the bot runs it)"""
    import onnxruntime as ort
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    sp = json.loads(sess.get_modelmeta().custom_metadata_map["spec"])
    for i in range(len(ref["s"])):
        got = sess.run(None, {k: ref[k][i:i + 1] for k in ("s", "ent", "grid", "h")})
        for k, g in zip(OUTS, got):
            ok = ref[k][i:i + 1] > -1e8   # masked logits: compared by being masked
            assert ((g > -1e8) == ok).all(), (k, i)
            np.testing.assert_allclose(g[ok], ref[k][i:i + 1][ok], atol=1e-4, err_msg=f"{k} row {i}")
    return sp


def load_net(ckpt):
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    sd = ck.get("model", ck) if isinstance(ck, dict) else ck
    net = Mo.Policy(); net.load_state_dict(sd, strict=False)
    if isinstance(ck, dict) and ck.get("obs_version") not in (None, O.OBS_VERSION):
        print("checkpoint obs %s, exporting as %s (new input columns zero-padded)" % (ck["obs_version"], O.OBS_VERSION))
    args = (ck.get("args") or {}) if isinstance(ck, dict) else {}
    return net, (ck.get("update") if isinstance(ck, dict) else None), int(args.get("gadgets") or 0) > 0, int(args.get("hyper") or 0) > 0


def _check():
    import tempfile
    torch.manual_seed(0)
    table = hero_table()
    assert len(table) == len(O.hero_names()) and all(len(v["stats"]) == 13 for v in table.values())
    assert table["shelly"]["name"] == "ShotgunGirl" and table["shelly"]["display"] == "SHELLY", table.get("shelly")
    assert table["piper"]["name"] == "Sniper" and abs(table["shelly"]["speed"] - 770 / 6000) < 1e-9
    assert np.allclose(table["piper"]["stats"], O.brawler_stats("Sniper"), atol=1e-6)
    assert resolve_trained(["Sniper", "colt"], table) == ["piper", "colt"]
    net = Mo.Policy(); net.add_heroes([O.brawler_stats("Sniper")])
    with torch.no_grad(): net.fire_x.weight.normal_(0, 0.3)   # a policy that uses the gadget and hypercharge classes
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "policy_chk_u0.onnx")
        sp = spec("chk/u0", ["piper"], table, hyper=True)
        ref = export(net, out, sp, n_ref=16)
        got = check_onnx(out, ref)
        assert got["obs_version"] == O.OBS_VERSION and got["n_s"] == O.N_SELF + O.N_COND + O.N_INT and got["f_ent"] == O.F_ENT
        assert got["fire"] == list(O.FIRE) and got["hyper"] and not got["gadgets"] and got["trained"] == ["piper"] and "piper" in got["heroes"]
        r = np.load(out[:-5] + ".ref.npz")
        assert r["fire"].shape == (16, len(O.FIRE)) and r["h_out"].shape == (16, Mo.HID)
        off = r["s"][:, 3] < 0.5; assert (r["fire"][off, 3] < -1e8).all() and (r["fire"][~off, 3] > -1e8).all()   # gadget gate
        H = O.FIRE.index("hypercharge"); off = r["s"][:, 4] < 0.5
        assert off.any() and (~off).any() and (r["fire"][off, H] < -1e8).all() and (r["fire"][~off, H] > -1e8).all()   # hypercharge gate
    print("export_policy check ok: %d heroes, spec %d bytes" % (len(table), len(json.dumps(sp))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ckpt", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--trained", default="Sniper", help="comma list: characters.csv names or item names")
    ap.add_argument("--name", default="", help="ckpt label in the spec (default: run folder / u<update>)")
    ap.add_argument("--team", type=int, default=1, help="team size the bot assumes before it reads the HUD")
    ap.add_argument("--ticks", type=int, default=2, help="game ticks per decision (the trainer's)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check: return _check()
    assert a.ckpt and a.out and a.out.endswith(".onnx"), "usage: python -m export_policy CKPT OUT.onnx --trained ..."
    net, upd, gadgets, hyper = load_net(a.ckpt)
    table = hero_table(); trained = resolve_trained(a.trained.split(","), table)
    name = a.name or "%s/u%s" % (os.path.basename(os.path.dirname(os.path.abspath(a.ckpt))), upd if upd is not None else "?")
    ref = export(net, a.out, spec(name, trained, table, a.team, a.ticks, gadgets, hyper))
    check_onnx(a.out, ref)
    print(f"wrote {a.out} (+ .ref.npz): obs {O.OBS_VERSION}, trained {trained}, {name}")


if __name__ == "__main__":
    sys.exit(main())
