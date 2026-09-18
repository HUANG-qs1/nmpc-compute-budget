#!/usr/bin/env python3
"""replay_render.py v2.2 —— 从实验 dump NPZ 回放状态并离屏渲染（零新实验、零时序污染）。
v2.2: 机体按 DJI Mavic 4 Pro 形态语言重做（深灰流线机身/机首大球云台/黑桨橙尖/前避障双目/
      电机银环/无雪橇仅前足小撑脚），场景改深色高级感（炭蓝渐变天空+暗棋盘地板+雾+三点光）。
      全部运行时注入，物理 quad.xml 不动一个字节；拖尾 decor 几何修复三连坑：
      label 未初始化乱码（必须 g.label=""，str，bytes 会段错误）、mjvGeom 代理被 GC 回收段错误
      （模块级 _TRAIL_KEEP 持有引用）、同一 Renderer 跨 update_scene 复用导致 decor 属性错乱
      （每帧派独立子进程渲染，进程边界隔离跨帧状态）。
用法:
  python3 replay_render.py DUMP.npz OUTDIR [--frames a,b,c | --every N]
         [--width 1600 --height 1200] [--az -25 --el -13 --dist 1.2] [--no-trail]
"""
import argparse, math, os, sys
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from PIL import Image


def srgb2lin(c):
    c = np.asarray(c, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

# Okabe-Ito（与 FIGSPEC §3 一致，经 sRGB->linear 转换）
TRAIL = {
    "fixed20":  srgb2lin(hx("D55E00")),
    "reactive": srgb2lin(hx("E69F00")),
    "v3":       srgb2lin(hx("0072B2")),
}
TRAIL_DEFAULT = srgb2lin(hx("D55E00"))

# ---- 场景注入（纯视觉）：深色高级感，不亮 ----
VISUAL_INJECT = """
<visual>
  <global offwidth="{off_w}" offheight="{off_h}"/>
  <quality shadowsize="4096"/>
  <map fogstart="10" fogend="34"/>
  <headlight ambient="0.38 0.38 0.40" diffuse="0.50 0.50 0.53" specular="0 0 0"/>
</visual>
"""

ASSET_INJECT = """
<asset>
  <texture name="sky" type="skybox" builtin="gradient"
           rgb1="{sky_top}" rgb2="{sky_bot}" width="512" height="512"/>
  <texture name="floor" type="2d" builtin="checker" mark="none"
           rgb1="{floor_a}" rgb2="{floor_b}" width="512" height="512"/>
  <material name="floor" texture="floor" texrepeat="6 6" texuniform="true"
            reflectance="0.10"/>
</asset>
"""

WORLD_INJECT = """
<geom name="floor" type="plane" pos="0 0 0" size="30 30 0.1" material="floor"/>
<light name="key" directional="true" pos="3.5 -2.5 7" dir="-0.40 0.29 -0.86"
       diffuse="{key}" specular="0.25 0.25 0.25"/>
<light name="rim" directional="true" pos="-4 3 3.5" dir="0.72 -0.54 -0.63"
       diffuse="{rim}" specular="0.12 0.12 0.12"/>
<light name="fill" directional="true" pos="1 5 4" dir="-0.16 -0.78 -0.62"
       diffuse="{fill}" specular="0 0 0"/>
"""

def _fmt(c):
    return "{:.4f} {:.4f} {:.4f}".format(*c)

SCENE_COLORS = {
    "sky_top": _fmt(srgb2lin(hx("1E232A"))),   # 深炭蓝（天顶）
    "sky_bot": _fmt(srgb2lin(hx("3B434E"))),   # 地平线略亮
    "floor_a": _fmt(srgb2lin(hx("262B32"))),   # 暗棋盘 A
    "floor_b": _fmt(srgb2lin(hx("2C323B"))),   # 暗棋盘 B
    "key":  _fmt([1.38, 1.42, 1.52]),          # 冷白主光
    "rim":  _fmt([0.95, 0.72, 0.48]),          # 暖轮廓光
    "fill": _fmt([0.38, 0.44, 0.58]),          # 冷蓝补光
}

# ---- 机体美化配色（DJI Mavic 4 Pro 形态语言）----
C_HULL    = srgb2lin(hx("70747B"))   # 主壳（中灰，实机不是深灰）
C_HULL2   = srgb2lin(hx("585C63"))   # 次壳/机腹/座舱盖
C_ARM     = srgb2lin(hx("6E7278"))   # 机臂
C_MOTOR   = srgb2lin(hx("2F3237"))   # 电机座
C_RING    = srgb2lin(hx("9BA0A6"))   # 电机顶银环
C_BLADE   = srgb2lin(hx("292D33"))   # 桨叶（深灰黑）
C_TIP     = srgb2lin(hx("E8850C"))   # 桨尖橙
C_GIMBAL  = srgb2lin(hx("26292E"))   # 云台
C_LENS    = srgb2lin(hx("101215"))   # 镜头/传感窗
C_FRONT   = srgb2lin(hx("D55E00"))   # 前 LED（朱红）
C_BACK    = srgb2lin(hx("009E73"))   # 后 LED（青绿）


def _qz(deg):
    """绕 z 轴旋转角的四元数（w,x,y,z）。"""
    t = np.deg2rad(deg) / 2.0
    return "{:.5f} 0 0 {:.5f}".format(np.cos(t), np.sin(t))


def _qaxis(ax, ay, az, deg):
    """绕任意轴旋转的四元数（w,x,y,z）。"""
    n = math.sqrt(ax * ax + ay * ay + az * az)
    if n < 1e-12:
        ax, ay, az, n = 0.0, 0.0, 1.0, 1.0
    t = np.deg2rad(deg) / 2.0
    s = np.sin(t) / n
    return "{:.5f} {:.5f} {:.5f} {:.5f}".format(np.cos(t), ax * s, ay * s, az * s)


def beautify_quad(xml):
    """解析 quad.xml，定位机身盒与四个旋翼球，运行时注入 Mavic 4 Pro 风格外观件。
    原几何保留但换装（球缩小藏进电机座、盒改次壳色），新增件全部为同 body 视觉几何。
    返回 (新xml字符串, 旋翼位置列表)。仅用于回放渲染，不涉及任何动力学计算。"""
    root = ET.fromstring(xml)
    body = root.find(".//worldbody/body")
    assert body is not None, "quad.xml 中未找到 body"
    rotors = []   # (x, y, z, is_front_family)
    for g in body.findall("geom"):
        t = g.get("type", "sphere")
        pos = g.get("pos", "0 0 0")
        px, py, pz = (float(v) for v in pos.split())
        rgba = [float(v) for v in g.get("rgba", "0.5 0.5 0.5 1").split()]
        if t == "sphere" and (abs(px) > 0.05 or abs(py) > 0.05):
            is_front = rgba[0] > rgba[1]           # 原配色: 前红 后绿
            rotors.append((px, py, pz, is_front))
            g.set("size", "0.012")                  # 大球缩小藏进电机座
            g.set("rgba", "{:.4f} {:.4f} {:.4f} 1".format(*C_MOTOR))
        elif t == "box":
            g.set("size", "0.030 0.030 0.010")      # 原盒压扁藏进主壳
            g.set("rgba", "{:.4f} {:.4f} {:.4f} 1".format(*C_HULL2))
    assert len(rotors) == 4, "旋翼定位失败: 找到 %d 个（期望 4）" % len(rotors)

    # 前向 = 红色旋翼族均值方向；局部坐标系 P(fwd, side, up) -> 世界 xyz
    fx = np.mean([r[0] for r in rotors if r[3]])
    fy = np.mean([r[1] for r in rotors if r[3]])
    n = np.hypot(fx, fy)
    fx, fy = (fx / n, fy / n) if n > 1e-6 else (1.0, 0.0)
    sx, sy = -fy, fx                                # 侧向（左舷）
    theta = float(np.rad2deg(np.arctan2(fy, fx)))   # fwd 与 +x 的夹角

    def P(f, s, u):
        return (fx * f + sx * s, fy * f + sy * s, u)

    def geom(attrs):
        ET.SubElement(body, "geom", attrs)

    def rgb(c, a=1.0):
        return "{:.4f} {:.4f} {:.4f} {:.2f}".format(c[0], c[1], c[2], a)

    def xyz(p):
        return "{:.4f} {:.4f} {:.4f}".format(p[0], p[1], p[2])

    blade_angles = [25.0, 115.0, 70.0, 160.0]       # 四桨相位错开，静态更真实
    for i, (px, py, pz, is_front) in enumerate(rotors):
        r = np.hypot(px, py); ux, uy = px / r, py / r
        # 机臂: 根粗(0.012) 梢细(0.0075) 两段 capsule，自壳缘连到电机座
        geom({"type": "capsule", "contype": "0", "conaffinity": "0",
              "fromto": "{:.4f} {:.4f} 0.008 {:.4f} {:.4f} 0.004".format(
                  ux * 0.045, uy * 0.045, ux * 0.105, uy * 0.105),
              "size": "0.012", "rgba": rgb(C_ARM)})
        geom({"type": "capsule", "contype": "0", "conaffinity": "0",
              "fromto": "{:.4f} {:.4f} 0.004 {:.4f} {:.4f} 0.002".format(
                  ux * 0.105, uy * 0.105, px * 0.985, py * 0.985),
              "size": "0.0075", "rgba": rgb(C_ARM)})
        # 电机座 + 顶部银环
        geom({"type": "cylinder", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.004".format(px, py), "size": "0.019 0.008",
              "rgba": rgb(C_MOTOR)})
        geom({"type": "cylinder", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.0135".format(px, py), "size": "0.011 0.0025",
              "rgba": rgb(C_RING)})
        # 桨毂
        geom({"type": "sphere", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.020".format(px, py), "size": "0.008",
              "rgba": rgb(C_MOTOR)})
        # 两叶细桨（主视觉，近黑）+ 淡淡桨盘（暗示扫掠面，alpha 0.05）
        phi = blade_angles[i]
        ca, sa = np.cos(np.deg2rad(phi)), np.sin(np.deg2rad(phi))
        geom({"type": "box", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.024".format(px, py),
              "size": "0.105 0.0078 0.0008",
              "quat": _qz(phi), "rgba": rgb(C_BLADE, 0.96)})
        # 橙尖（黑桨橙尖，Mavic 标志细节）：桨向两端 ±0.096
        for sgn in (+1.0, -1.0):
            geom({"type": "box", "contype": "0", "conaffinity": "0",
                  "pos": "{:.4f} {:.4f} 0.024".format(px + sgn * 0.096 * ca,
                                                      py + sgn * 0.096 * sa),
                  "size": "0.010 0.0082 0.0009",
                  "quat": _qz(phi), "rgba": rgb(C_TIP)})
        geom({"type": "cylinder", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.024".format(px, py), "size": "0.106 0.0004",
              "rgba": rgb(C_RING, 0.035)})
        # 臂梢 LED（前朱红/后青绿，俯视可读）
        cap = C_FRONT if is_front else C_BACK
        geom({"type": "sphere", "contype": "0", "conaffinity": "0",
              "pos": "{:.4f} {:.4f} 0.012".format(px * 0.85, py * 0.85),
              "size": "0.006", "rgba": rgb(cap)})

    # ---- 机身（Mavic 4 Pro：流线主壳 + 机首大球云台，无雪橇）----
    # 主壳：前向扁椭球
    geom({"type": "ellipsoid", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(0.004, 0.0, 0.002)), "size": "0.072 0.052 0.027",
          "quat": _qz(theta), "rgba": rgb(C_HULL)})
    # 尾部收束椭球
    geom({"type": "ellipsoid", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(-0.055, 0.0, 0.010)), "size": "0.034 0.038 0.016",
          "quat": _qz(theta), "rgba": rgb(C_HULL)})
    # 顶部座舱盖（略深，勾出层次）
    geom({"type": "ellipsoid", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(-0.012, 0.0, 0.024)), "size": "0.030 0.028 0.008",
          "quat": _qz(theta), "rgba": rgb(C_HULL2)})
    # 机腹电池仓（扁平椭球，避免盒-壳 z-fighting）
    geom({"type": "ellipsoid", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(-0.008, 0.0, -0.020)), "size": "0.050 0.042 0.016",
          "quat": _qz(theta), "rgba": rgb(C_HULL2)})
    # 尾部散热口（深色细条）
    geom({"type": "box", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(-0.082, 0.0, 0.006)), "size": "0.006 0.020 0.006",
          "quat": _qz(theta), "rgba": rgb(C_GIMBAL)})
    # 机首标志性大球云台
    geom({"type": "sphere", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(0.066, 0.0, -0.006)), "size": "0.030",
          "rgba": rgb(C_GIMBAL)})
    # 云台前向镜头：主镜 + 副镜（双 cylinder，轴向朝前）
    lq = _qaxis(-fy, fx, 0.0, 90.0)
    geom({"type": "cylinder", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(0.092, 0.008, -0.003)), "size": "0.011 0.0045",
          "quat": lq, "rgba": rgb(C_LENS)})
    geom({"type": "cylinder", "contype": "0", "conaffinity": "0",
          "pos": xyz(P(0.094, -0.009, -0.014)), "size": "0.0055 0.004",
          "quat": lq, "rgba": rgb(C_LENS)})
    # 前避障双目（机首上缘两小窗）
    for sgn in (+1.0, -1.0):
        geom({"type": "sphere", "contype": "0", "conaffinity": "0",
              "pos": xyz(P(0.040, sgn * 0.020, 0.020)), "size": "0.0055",
              "rgba": rgb(C_LENS)})
    # 前足小撑脚（Mavic 无雪橇，仅机腹前侧两小足）
    for sgn in (+1.0, -1.0):
        a = P(0.030, sgn * 0.040, -0.018)
        b = P(0.034, sgn * 0.046, -0.046)
        geom({"type": "capsule", "contype": "0", "conaffinity": "0",
              "fromto": "{:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f}".format(
                  a[0], a[1], a[2], b[0], b[1], b[2]),
              "size": "0.005", "rgba": rgb(C_ARM)})

    return ET.tostring(root, encoding="unicode"), [(r[0], r[1], r[2]) for r in rotors]


def build_render_xml(quad_xml, off_w, off_h):
    """在原 quad.xml 文本上注入视觉元素（字符串注入，不改文件一个字节）。"""
    xml = quad_xml
    i = xml.index(">", xml.index("<mujoco")) + 1
    xml = xml[:i] + VISUAL_INJECT.format(off_w=off_w, off_h=off_h) + xml[i:]
    xml = xml[:i] + ASSET_INJECT.format(**SCENE_COLORS) + xml[i:]
    j = xml.index(">", xml.index("<worldbody")) + 1
    xml = xml[:j] + WORLD_INJECT.format(**SCENE_COLORS) + xml[j:]
    return xml


def rpy2quat(roll, pitch, yaw):
    cr, sr = np.cos(roll / 2), np.sin(roll / 2)
    cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
    cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ])


def load_x12(npz_path):
    d = np.load(npz_path, allow_pickle=True)
    keys = list(d.keys())
    print("[check] NPZ keys:", keys)
    key = "x12" if "x12" in keys else "x12_log"
    assert key in keys, "x12/x12_log 均不在 NPZ 中，实际键: %s" % keys
    x = np.asarray(d[key])
    meta = {k: d[k].item() if np.asarray(d[k]).ndim == 0 else d[k]
            for k in ("task", "method", "pattern", "seed") if k in keys}
    if x.shape[1] == 13:
        layout = "quat"
    elif x.shape[1] == 12:
        layout = "euler"
    else:
        raise ValueError("未知状态维数 %d" % x.shape[1])
    print("[check] %s: %s, layout=%s, meta=%s" % (key, x.shape, layout, meta))
    return x, layout, meta


# 模块级持有：mjvGeom 代理必须活到 render 之后，GC 回收会丢属性/段错误
_TRAIL_KEEP = []
_ZERO3 = np.zeros(3)
_EYE9 = np.eye(3).flatten()

def add_trail(scene, positions, rgba, width=0.012):
    """沿轨迹点列加 capsule 拖尾（decor 几何）。
    微段(<12 mm)跳过防悬停淤积；中点距机体当前位置 <6 cm 的段跳过，拖尾不碰机身。
    注意：mjv_makeScene 不零初始化 geom 槽（texid/matid/rgba/label 全是垃圾值），
    模型一有纹理/材质，垃圾 texid 会把拖尾渲黑甚至段错误 —— 必须先 mjv_initGeom 消毒。"""
    n0 = scene.ngeom
    _KEEP = _TRAIL_KEEP
    cur = np.asarray(positions[-1], dtype=float)
    for a, b in zip(positions[:-1], positions[1:]):
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if np.linalg.norm(b - a) < 1.2e-2:
            continue
        if np.linalg.norm((a + b) / 2.0 - cur) < 0.06:
            continue
        if scene.ngeom >= scene.maxgeom:
            break
        g = scene.geoms[scene.ngeom]
        if hasattr(mujoco, "mjv_initGeom"):
            mujoco.mjv_initGeom(g, mujoco.mjtGeom.mjGEOM_CAPSULE,
                                _ZERO3, _ZERO3, _EYE9,
                                (rgba[0], rgba[1], rgba[2], 0.95))
        else:
            g.texid = -1; g.matid = -1; g.dataid = -1
        mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_CAPSULE, width, a, b)
        g.rgba[:] = [rgba[0], rgba[1], rgba[2], 0.95]
        g.label = ""            # initGeom 已置空，双保险；bytes 会段错误，必须 str
        g.emission = 0.85       # 自发光提亮，暗场景下保持 Okabe-Ito 可读性
        g.texid = -1            # 双保险：绝不绑纹理/材质
        g.matid = -1
        _KEEP.append(g)
        scene.ngeom += 1
    return scene.ngeom - n0


def render_one(args, model, data, x, layout, trail_rgba, t):
    """渲染单帧（在本进程内只被调用一次；跨帧状态隔离由父进程的子进程边界保证）。"""
    if layout == "quat":
        data.qpos[:3] = x[t, 0:3]; data.qpos[3:7] = x[t, 3:7]
    else:
        data.qpos[:3] = x[t, 0:3]; data.qpos[3:7] = rpy2quat(*x[t, 3:6])
    mujoco.mj_forward(model, data)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = x[t, 0:3]
    cam.distance = args.dist
    cam.azimuth = args.az
    cam.elevation = args.el
    renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    renderer.update_scene(data, camera=cam)
    n_seg = 0
    if not args.no_trail:
        lo = max(0, t - args.trail_len + 1)
        n_seg = add_trail(renderer.scene, x[lo:t + 1, 0:3], trail_rgba)
    img = renderer.render()
    std = float(img.std())
    assert std > 1.0, "帧 %d 疑似黑屏/空画面 (std=%.2f)" % (t, std)
    path = os.path.join(args.outdir, "frame_%04d.png" % t)
    Image.fromarray(img).save(path)
    print("[frame] %s  std=%.1f  trail=%d" % (path, std, n_seg), flush=True)


def main():
    import subprocess as sp
    ap = argparse.ArgumentParser()
    ap.add_argument("dump"); ap.add_argument("outdir")
    ap.add_argument("--frames", default=None, help="逗号分隔帧号，如 60,63,66")
    ap.add_argument("--every", type=int, default=None, help="每隔 N 帧渲一帧")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--az", type=float, default=-25.0)
    ap.add_argument("--el", type=float, default=-13.0)
    ap.add_argument("--dist", type=float, default=1.2)
    ap.add_argument("--no-trail", action="store_true")
    ap.add_argument("--trail-len", type=int, default=150)
    ap.add_argument("--_worker", type=int, default=None,
                    help="内部参数：子进程只渲染这一帧（隔离跨帧渲染状态）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "quad.xml"), "r") as f:
        quad_xml = f.read()

    x, layout, meta = load_x12(args.dump)
    T = x.shape[0]

    if args._worker is None:
        # 父进程：每帧派一个独立子进程渲染（v2.2 实锤：同进程跨帧 decor 几何会段错误/
        # 颜色错乱，根因在 MuJoCo 场景缓冲复用；子进程边界是最彻底的隔离，零状态共享）
        if args.frames:
            frames = [int(s) for s in args.frames.split(",")]
        elif args.every:
            frames = list(range(0, T, args.every))
        else:
            frames = [0, T // 2, T - 1]
        frames = [t for t in frames if 0 <= t < T]
        print("[check] T=%d, 渲染 %d 帧: %s%s" % (T, len(frames), frames[:10], "..." if len(frames) > 10 else ""))
        os.makedirs(args.outdir, exist_ok=True)
        fwd = ["--width", str(args.width), "--height", str(args.height),
               "--az", str(args.az), "--el", str(args.el), "--dist", str(args.dist),
               "--trail-len", str(args.trail_len)]
        if args.no_trail:
            fwd.append("--no-trail")
        for t in frames:
            png = os.path.join(args.outdir, "frame_%04d.png" % t)
            cmd = [sys.executable, os.path.abspath(__file__), args.dump, args.outdir,
                   "--_worker", str(t)] + fwd
            r = sp.run(cmd)
            assert r.returncode == 0, "帧 %d 子进程失败 rc=%d" % (t, r.returncode)
            assert os.path.exists(png), "帧 %d 未产出 %s" % (t, png)
        print("[done] %d 帧写入 %s" % (len(frames), args.outdir))
        return

    # 子进程：本进程只渲染 args._worker 这一帧
    t = args._worker
    assert 0 <= t < T, "帧号 %d 越界 [0,%d)" % (t, T)
    render_xml = build_render_xml(quad_xml, max(args.width, 1920), max(args.height, 1440))
    render_xml, rotors = beautify_quad(render_xml)
    print("[check] beautify: 旋翼位置 = %s" % (["(%+.2f,%+.2f)" % (r[0], r[1]) for r in rotors]))
    model = mujoco.MjModel.from_xml_string(render_xml)
    data = mujoco.MjData(model)

    method = str(meta.get("method", "")).lower()
    stem = os.path.basename(args.dump).lower()
    if method not in TRAIL:
        if "fixed20" in stem or "f20" in stem:
            method = "fixed20"
        elif "reactive" in stem:
            method = "reactive"
        elif "v3" in stem:
            method = "v3"
    trail_rgba = TRAIL.get(method, TRAIL_DEFAULT)
    print("[check] trail method=%s tick=%d" % (method, t))

    os.makedirs(args.outdir, exist_ok=True)
    render_one(args, model, data, x, layout, trail_rgba, t)


if __name__ == "__main__":
    main()
