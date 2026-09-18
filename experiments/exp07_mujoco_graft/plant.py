"""MuJoCo quadrotor plant v2 (amendment i).
Mismatch arm compiles a second model from modified XML text,
guaranteeing mass-matrix / bias-force consistency."""
import mujoco
import numpy as np
import os

XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quad.xml")

class QuadPlant:
    def __init__(self, mm=0.0, dt=0.01):
        with open(XML) as f:
            xml = f.read()
        self.mass_nominal = 1.0
        if mm != 0.0:
            m = self.mass_nominal * (1.0 + mm)
            i0, iz0 = 0.006 * (1.0 + mm), 0.011 * (1.0 + mm)
            xml = xml.replace('mass="1.0"', f'mass="{m:.6f}"')
            xml = xml.replace('diaginertia="0.006 0.006 0.011"',
                              f'diaginertia="{i0:.6f} {i0:.6f} {iz0:.6f}"')
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.dt = dt
        self.model.opt.timestep = dt
        self.data = mujoco.MjData(self.model)
        self.mass = self.mass_nominal * (1.0 + mm)

    def reset(self, pos=(0, 0, 1.0), seed=None):
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:3] = pos
        self.data.qpos[3:7] = [1, 0, 0, 0]
        if seed is not None:
            rng = np.random.default_rng(seed)
            self.data.qpos[:3] += rng.uniform(-0.05, 0.05, 3)
            self.data.qvel[:3] += rng.uniform(-0.02, 0.02, 3)
        mujoco.mj_forward(self.model, self.data)

    def state(self):
        return np.concatenate([self.data.qpos[:3].copy(),
                               self.data.qpos[3:7].copy(),
                               self.data.qvel[:3].copy(),
                               self.data.qvel[3:6].copy()])

    def step(self, ctrl):
        self.data.ctrl[:] = np.clip(ctrl, [0, -1, -1, -0.5], [20, 1, 1, 0.5])
        mujoco.mj_step(self.model, self.data)
