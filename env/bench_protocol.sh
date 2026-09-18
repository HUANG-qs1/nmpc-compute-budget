#!/usr/bin/env bash
# bench_protocol.sh - 平台协议锁定 v1（预注册一半）
# 用法: source env/bench_protocol.sh 之后再跑实验脚本
set -x
# 1. 记录 CPU 信息与调频策略
lscpu | grep -E "Model name|CPU\(s\)|MHz" > env/cpu_info.txt
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null \
    > env/cpu_governor.txt || echo "no cpufreq (WSL)" > env/cpu_governor.txt
# 2. 环境变量记录
env | sort > env/env_vars_$(date +%Y%m%d).txt
python -c "import sys,casadi,numpy;print(sys.version);print('casadi',casadi.__version__);print('numpy',numpy.__version__)" \
    > env/runtime_versions.txt 2>&1
# 3. 单进程线程数锁定（防 BLAS 多线程抖动）
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
echo "threads locked: OMP=$OMP_NUM_THREADS"
set +x
