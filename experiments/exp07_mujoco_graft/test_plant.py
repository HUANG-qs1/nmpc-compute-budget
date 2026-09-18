"""Module-1 self-check v2: precharge actuator state to remove filter ramp transient."""
import numpy as np
from plant import QuadPlant

ok = True
# 1) hover: precharge act to m*g, 300 steps -> z drift < 2cm
p = QuadPlant(dt=0.01); p.reset(pos=(0, 0, 1.0))
p.data.act[:] = [p.mass * 9.81, 0, 0, 0]
for _ in range(300):
    p.step([p.mass * 9.81, 0, 0, 0])
z = p.state()[2]
r1 = abs(z - 1.0) < 0.02
print(f"hover   : z={z:.4f} (target 1.0 +/- 0.02) -> {'PASS' if r1 else 'FAIL'}")
ok &= r1
# 2) free fall: zero thrust, 1s -> dz ~= 0.5*g within 2%
p2 = QuadPlant(dt=0.01); p2.reset(pos=(0, 0, 1.0))
for _ in range(100):
    p2.step([0, 0, 0, 0])
dz = 1.0 - p2.state()[2]
r2 = abs(dz - 4.905) / 4.905 < 0.02
print(f"freefall: dz={dz:.4f} (target 4.905 +/- 2%) -> {'PASS' if r2 else 'FAIL'}")
ok &= r2
# 3) mismatch arm: precharge 9.81N vs 1.2kg weight -> sink ~0.82m in 1s
p3 = QuadPlant(mm=0.20, dt=0.01); p3.reset(pos=(0, 0, 1.0))
p3.data.act[:] = [9.81, 0, 0, 0]
for _ in range(100):
    p3.step([9.81, 0, 0, 0])
z3 = p3.state()[2]
r3 = 0.10 < z3 < 0.30 and abs(p3.mass - 1.2) < 1e-9
print(f"mismatch: z={z3:.4f}, mass={p3.mass:.3f} (expect ~0.18, 1.2) -> {'PASS' if r3 else 'FAIL'}")
ok &= r3
print("MODULE1:", "ALL PASS" if ok else "FAIL - do not proceed")
