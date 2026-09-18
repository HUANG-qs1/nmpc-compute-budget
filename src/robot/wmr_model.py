import numpy as np

class MPCController:
    """简单 MPC 轨迹跟踪控制器"""
    def __init__(self, dt=0.1, N=10):
        self.dt = dt
        self.N = N  # 预测步数
        
    def solve(self, x_current, ref_segment):
        x, y, theta = x_current
        x_ref, y_ref = ref_segment[0]
        
        # 位置误差
        ex = x_ref - x
        ey = y_ref - y
        
        # 旋转到机器人坐标系
        e_x_body = np.cos(theta) * ex + np.sin(theta) * ey
        e_y_body = -np.sin(theta) * ex + np.cos(theta) * ey
        
        # 简单 PD 控制
        v = 0.5 * e_x_body + 0.3
        omega = 2.0 * np.arctan2(e_y_body, e_x_body + 0.1)
        
        # 限幅
        v = np.clip(v, -1.0, 1.0)
        omega = np.clip(omega, -1.0, 1.0)
        
        return np.array([v, omega])
