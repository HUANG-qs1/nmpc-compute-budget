import re
src = open("quad_nmpc.py").read()
src = src.replace(
    "import sys, time\nimport numpy as np",
    "import sys, time, signal\nimport numpy as np")
src = src.replace(
    'LAST_STATS = {"success": True, "iter_count": 0}',
    'LAST_STATS = {"success": True, "iter_count": 0}\n'
    'SOLVE_CAP_S = 3.0  # watchdog: legit solves q95~171ms; 3s only kills pathological ones\n'
    'class _SolveTimeout(Exception):\n    pass\n'
    'def _alarm_handler(sig, frm):\n    raise _SolveTimeout()\n'
    'signal.signal(signal.SIGALRM, _alarm_handler)')
src = src.replace(
    """    try:
        sol = opti.solve()""",
    """    signal.setitimer(signal.ITIMER_REAL, SOLVE_CAP_S)
    try:
        sol = opti.solve()""")
src = src.replace(
    """    except Exception:
        LAST_STATS["success"] = False
        LAST_STATS["iter_count"] = 200
        return U_HOVER.copy()""",
    """    except (Exception, _SolveTimeout):
        LAST_STATS["success"] = False
        LAST_STATS["iter_count"] = 200
        signal.setitimer(signal.ITIMER_REAL, 0)
        return U_HOVER.copy()
    signal.setitimer(signal.ITIMER_REAL, 0)""")
open("quad_nmpc.py", "w").write(src)
print("patched")
