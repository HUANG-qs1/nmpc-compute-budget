"""replay_render.py v1.0 — F9 渲染帧回放器（D51-a 定案，D52 沙盒自核验通过）
从 dump NPZ 的 x12_log 重放状态并离屏渲染。零新实验、零时序污染（⑱合规）。
quad.xml 本体不改：地板/光照/相机/离屏缓冲在运行时注入（沿用 mismatch 臂惯例）。
用法:
  python3 replay_render.py DUMP.npz OUTDIR [--frames 90,180,300,470] [--every N]
          [--width 1600 --height 1200] [--az 60 --el -20 --dist 2.0] [--no-trail]
"""
import argparse, os
import numpy as np
import mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, "quad.xml")

# Okabe-Ito（sRGB）→ linear（MuJoCo 渲染管线对 decor 几何做 gamma 输出，必须先转 linear，D52 自核验发现）
def srgb2lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
TRAIL = {"fixed20": (213, 94, 0), "v3": (0, 114, 178), "reactive": (230, 159, 0)}  # FIGSPEC §3

VISUAL = """  <visual>
    <global offwidth="{W}" offheight="{H}"/>
    <quality shadowsize="4096"/>
    <headlight ambient="0.35 0.35 0.35" diffuse="0.25 0.25 0.25" specular="0 0 0"/>
  </visual>
"""
ASSET = """  <asset>
    <texture name="floor_tex" type="2d" builtin="checker" width="256" height="256" rgb1="0.95 0.95 0.95" rgb2="0.78 0.78 0.78"/>
    <material name="floor_mat" texture="floor_tex" texrepeat="4 4" reflectance="0.03"/>
  </asset>
"""
WORLD_INJECT = """    <geom name="floor" type="plane" pos="0 0 0" size="12 12 0.1" material="floor_mat"/>
    <light name="key"  pos="2 2 5"   dir="-0.35 -0.35 -1" diffuse="0.65 0.65 0.65" specular="0.1 0.1 0.1"/>
    <light name="fill" pos="-3 -1 3" dir="0.55 0.2 -1"    diffuse="0.3 0.3 0.32"/>
"""

def build_render_xml(off_w, off_h):
    with open(XML) as f:
        xml = f.read()
    assert "<worldbody>" in xml
    vis = VISUAL.format(W=off_w, H=off_h)
    return xml.replace("<worldbody>", vis + ASSET + "  <worldbody>\n" + WORLD_INJECT, 1)

def rpy2quat(roll, pitch, yaw):  # -> wxyz
    cr, sr = np.cos(roll/2), np.sin(roll/2)
    cp, sp = np.cos(pitch/2), np.sin(pitch/2)
    cy, sy = np.cos(yaw/2), np.sin(yaw/2)
    return np.array([cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy,
                     cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy])

def load_x12(npz):
    z = np.load(npz, allow_pickle=False)
    keys = list(z.keys())
    print("[check] NPZ keys:", keys)
    key = "x12" if "x12" in keys else "x12_log"
    assert key in keys, "x12/x12_log 不在 NPZ 中，实际键: %s" % keys
    x = np.asarray(z[key], dtype=np.float64)
    assert x.ndim == 2, "x12_log 维度异常: %s" % (x.shape,)
    layout = {13: "quat", 12: "euler"}.get(x.shape[1])
    assert layout, "x12_log 宽度异常: %s（期望 12 或 13）" % (x.shape,)
    meta = {k: z[k].item() for k in ("task", "method", "pattern", "seed") if k in keys}
    print("[check] x12_log: %s, layout=%s, meta=%s" % (x.shape, layout, meta))
    return x, layout, meta

def add_trail(scene, pts, rgba_lin, width=0.012):
    n = 0
    for i in range(len(pts) - 1):
        if scene.ngeom >= scene.maxgeom:
            break
        a, b = pts[i], pts[i + 1]
        if np.linalg.norm(b - a) < 1e-9:   # 退化段会污染渲染，跳过
            continue
        g = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(g, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3),
                            np.zeros(3), np.eye(3).flatten(), rgba_lin.astype(np.float32))
        mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_CAPSULE, width, a, b)
        scene.ngeom += 1
        n += 1
    return n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz"); ap.add_argument("outdir")
    ap.add_argument("--frames", default=None, help="逗号分隔 tick 列表，如 90,180,300,470")
    ap.add_argument("--every", type=int, default=None, help="均匀抽帧间隔（与 --frames 二选一）")
    ap.add_argument("--width", type=int, default=1600); ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--az", type=float, default=60.0); ap.add_argument("--el", type=float, default=-20.0)
    ap.add_argument("--dist", type=float, default=2.0)
    ap.add_argument("--no-trail", action="store_true")
    args = ap.parse_args()

    x12, layout, meta = load_x12(args.npz)
    T = x12.shape[0]
    if args.frames:
        ticks = [int(s) for s in args.frames.split(",")]
    else:
        step = args.every or max(1, T // 8)
        ticks = list(range(0, T, step))
    ticks = [t for t in ticks if 0 <= t < T]
    assert ticks, "无有效帧号"
    print("[check] T=%d, 渲染 %d 帧: %s" % (T, len(ticks), ticks[:20]))

    model = mujoco.MjModel.from_xml_string(build_render_xml(args.width, args.height))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE

    rgba_lin = srgb2lin(TRAIL.get(str(meta.get("method", "")), (0, 114, 178)))
    rgba_lin = np.concatenate([rgba_lin, [1.0]])

    os.makedirs(args.outdir, exist_ok=True)
    for tick in ticks:
        row = x12[tick]
        data.qpos[:3] = row[0:3]
        data.qpos[3:7] = row[3:7] if layout == "quat" else rpy2quat(*row[3:6])
        mujoco.mj_forward(model, data)
        cam.lookat = row[0:3]; cam.distance = args.dist
        cam.azimuth = args.az; cam.elevation = args.el
        renderer.update_scene(data, camera=cam)
        ntrail = 0 if args.no_trail else add_trail(renderer.scene, x12[:tick+1, 0:3], rgba_lin)
        img = renderer.render()
        out = os.path.join(args.outdir, "frame_%04d.png" % tick)
        from PIL import Image
        Image.fromarray(img).save(out)
        assert img.std() > 1.0, "帧 %d 疑似黑屏（std=%.2f）" % (tick, img.std())
        print("[frame] %s  std=%.1f  trail=%d" % (out, img.std(), ntrail))
    print("[done] %d 帧写入 %s" % (len(ticks), args.outdir))

if __name__ == "__main__":
    main()
