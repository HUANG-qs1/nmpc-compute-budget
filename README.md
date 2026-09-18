# nmpc-compute-budget

Code, frozen run-level data, preregistration documents, and the analysis/figure
pipeline for the paper:

**Closed-loop survival of nonlinear MPC under time-varying compute budgets:
mechanisms and timeout-input policies**
(submitted to *Control Engineering Practice*, 2026)

## Repository layout

- `src/` — solver and calibration library (CasADi/IPOPT NMPC, the budget-aware
  control law v3, envelope calibration).
- `experiments/` — experiment runners and frozen artifacts, one directory per
  experiment:
  - `exp07_mujoco_graft/` — quadrotor (MuJoCo) main experiment, 1080 runs
    (seeds 230–244); also hosts `exp10_quad.csv` (720 runs, preregistered
    extension arms fixed10 and best-so-far).
  - `exp08_burst_scan/` — quadrotor burst-length dose scan, 600 runs
    (seeds 330–344).
  - `exp09_wmr_regress/` — wheeled mobile robot dose experiments, 300 runs
    (seeds 430–444); also hosts `exp10_wmr.csv` (60 runs).
  - `exp00_bench` … `exp06_phase_g1` — exploratory/calibration code from the
    exploration phase (runners, configs, and verdict files; their bulk CSV
    logs are deposited in the Zenodo archive, see below).
  - `verdicts_*.txt` — mechanically executed verdict files; the `analyze_*.py`
    scripts encode the frozen criteria and execute the verdicts.
- `docs/` — preregistration documents:
  - `preregistration_v0.md`, `preregistration_v1.md`,
    `preregistration_v1_1.md` — registration of the *early* experimental line
    (exp01–exp06 era; the line reported in the paper's Discussion as sealed
    ablation evidence).
  - `PLAN.md` — signed design freezes and the preregistered criteria for
    propositions P1–P6 of the reported line (entries D44–D49, each signed
    before data collection).
  - Originals are in Chinese; the manuscripts' English text corresponds to
    these records.
- `env/` — experiment-time environment records: `requirements_freeze.txt`,
  `runtime_versions.txt`, `cpu_info.txt`, and `bench_protocol.sh`
  (thread-count locking protocol).
- `analysis/` — figure pipeline (`make_figs.py`, `make_figs_v5.py`) and the
  audit script (`audit_M1_F2.py`) that recomputes the constraint-audit
  (Table 5) and gear-occupancy (Table 6) statistics from the frozen
  run-level logs.

## Frozen dataset

The registered dataset comprises **2760 runs**: exp07 (1080) + exp08 (600) +
exp09 (300) + exp10 (780). All randomness (budget sequences, initial
perturbations) is seed-controlled; the registered seed segments are 230–244
(exp07), 330–344 (exp08), and 430–444 (exp09). The seven frozen CSVs are kept
exactly as collected; smoke-test, fixture, and superseded files are excluded.

## Reproduce the statistics and figures

```bash
pip install -r env/requirements_freeze.txt
python3 analysis/audit_M1_F2.py   # recomputes Table 5 / Table 6 statistics (prints input counts)
python3 analysis/make_figs_v5.py  # regenerates the dose-response and summary figures into figs_out/
python3 analysis/make_figs.py     # regenerates the cross-platform cliff and dose-landscape figures
```

Every figure script asserts the frozen cell counts when the data are loaded;
any mismatch aborts the build.

## Experiment environment

The registered 2760 runs (exp07–exp10) all ran on a single host: a cloud
compute instance (Intel Xeon Platinum, 4 vCPUs, 8 GB RAM) running Ubuntu
24.04 LTS (kernel 6.8.0-137-generic); Python 3.11.15, CasADi 3.8.0, IPOPT
3.14.19 with MUMPS 5.8.2, MuJoCo 3.12.0; per-solve wall-clock timing via
Python `time.perf_counter()`. The earlier sealed experimental line
(exp01–exp06, seeds 100–129) ran on a laptop under WSL2; its environment is
documented in `env/` (`cpu_info.txt`, `runtime_versions.txt`,
`env_vars_20260902.txt`) and the two lines were never pooled
(see `docs/preregistration_v1_1.md`, amendment h.6).

## Archival DOI

A Zenodo archive of this repository (including the complete exploratory CSV
logs) will be linked here upon archiving.

## License

MIT (see `LICENSE`). Data files are released for verification and
reproduction of the paper's results.
