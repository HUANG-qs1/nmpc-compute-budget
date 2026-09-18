import numpy as np
from plant import QuadPlant
p = QuadPlant(mm=0.20, dt=0.01)
p.reset(pos=(0, 0, 1.0))
p.data.act[:] = [9.81, 0, 0, 0]
p.step([9.81, 0, 0, 0])
print("qacc[2]  =", p.data.qacc[2], " (expect -1.635 = 9.81/1.2 - 9.81)")
print("qfrc_actuator[2] =", p.data.qfrc_actuator[2])
print("body_mass =", p.model.body_mass)
print("subtree_mass =", p.model.subtree_mass)
print("act =", p.data.act.copy())
print("ctrl =", p.data.ctrl.copy())
