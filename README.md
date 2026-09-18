# nmpc-compute-budget

Code, frozen run-level data, preregistration documents, and the analysis/figure
pipeline for the paper:

**Closed-loop survival of nonlinear MPC under time-varying compute budgets:
mechanisms and timeout-input policies**
(submitted to *Control Engineering Practice*, 2026)

## Repository layout

- `src/` — solver and scheduling library:
  - `solver/nmpc_casadi.py` — CasADi/IPOPT NMPC core (WMR); shared simulation components.
  - `scheduler/compute_budgeter.py` — the budget-aware law v3 (L/M/H gear scheduling
    with EWMA, hysteresis, dwell time, timeout freeze, and online feasibility gates).
  - `scheduler/predictive_budgeter.py` — v3 + Markov one-step risk prediction.
  - `estimation/p2_quantile.py` — P2 online quantile estimator (per-gear q90 gates).
  - `calibration/kappa_estimate.py` — schedulability-prior (kappa) estimation.
  - `injection/` — budget sequence generation (`markov_seq.py`) and CPU load
    injection (`budget_injector.py`).
  - `robot/wmr_model.py` — wheeled mobile robot controller model.
- `experiments/` — experiment runners and frozen artifacts, one directory per
  registered experiment:
  - `exp07_mujoco_graft/` — quadrotor (MuJoCo) main experiment, 1080 runs
    (seeds 230–244): runner `run_graft.py`, batch driver `drive_batch.py`,
    graft layer `quad_nmpc.py`, plant `plant.py`, module self-checks
    (`test_plant.py`, `test_nmpc.py`, `test_cap_equiv.py`), gear-scan probes
    (`scan_gears.py`, `probe_iters.py`), watchdog patch (`patch_watchdog.py`),
    bite check (`verify_bite.py`), debug probe (`debug_mm.py`), render pipeline
    (`render_beat.py`, `replay_render.py`, `replay_render_v1_backup.py`),
    verdict instrument `analyze_graft.py`, verdict file
    `verdicts_exp07_srv2.txt`, and the frozen CSV (sharded, see below); also
    hosts `exp10_quad.csv` (720 runs, preregistered extension arms fixed10 and
    best-so-far).
  - `exp08_burst_scan/` — quadrotor burst-length dose scan, 600 runs
    (seeds 330–344): `run_scan.py`, batch driver `drive_scan.py`, verdict
    instrument `analyze_scan.py`, verdict file `verdicts_exp08_srv.txt`, and
    the frozen CSV.
  - `exp09_wmr_regress/` — wheeled mobile robot dose experiments, 300 runs
    (seeds 430–444): `run_regress.py`, cliff-localization instrument
    `l50_scan.py`, verdict instrument `analyze_regress.py`, three verdict
    files, and three frozen CSVs; also hosts `exp10_wmr.csv` (60 runs).
  - `verdicts_*.txt` — mechanically executed verdict files; the `analyze_*.py`
    scripts encode the frozen criteria and execute the verdicts.

  Exploratory-phase code (exp00–exp06, the sealed early line) is not part of
  this repository; its design records are the preregistration documents below,
  and its bulk CSV logs will be deposited in the Zenodo archive (see below).
- `docs/` — preregistration documents:
  - `preregistration_v0.md`, `preregistration_v1.md`,
    `preregistration_v1_1.md` — registration of the *early* experimental line
    (exp01–exp06 era; the line reported in the paper's Discussion as sealed
    ablation evidence).
  - `PLAN.md` — signed design freezes and the preregistered criteria for
    propositions P1–P6 of the reported line (entries D44–D49, each signed
    before data collection).
  - Originals are in Chinese; the manuscript's English text corresponds to
    these records.
- `env/` — experiment-time environment records: `requirements_freeze.txt`,
  `runtime_versions.txt`, `cpu_info.txt`, `cpu_governor.txt`, and
  `bench_protocol.sh` (thread-count locking protocol).
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

**exp07 CSV sharding.** The exp07 frozen CSV (1080 data rows) is stored as two
shards:

- `20260909_exp07_graft_srv2_seeds230-237.csv` (header + 576 rows)
- `20260909_exp07_graft_srv2_seeds238-244.csv` (header + 504 rows)

Reconstruct the original file before running the analysis/figure pipeline
(requires `bash` for process substitution):

```bash
cd experiments/exp07_mujoco_graft
cat 20260909_exp07_graft_srv2_seeds230-237.csv <(tail -n +2 20260909_exp07_graft_srv2_seeds238-244.csv) > 20260909_exp07_graft_srv2.csv
git hash-object 20260909_exp07_graft_srv2.csv
# expected: 7ec727bc51be8d28ce9606bd74e79cf03195ceeb
```

All analysis scripts (`analysis/*.py`, `experiments/*/analyze_*.py`) read the
reconstructed file.

## Reproduce the statistics and figures

```bash
pip install -r env/requirements_freeze.txt
# reconstruct the exp07 CSV first (see above)
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
documented in `env/` (`cpu_info.txt`, `runtime_versions.txt`) and the two
lines were never pooled (see `docs/preregistration_v1_1.md`, amendment h.6).

## Archival DOI

A Zenodo archive of this repository (including the complete exploratory CSV
logs) will be linked here upon archiving.

## License

MIT (see `LICENSE`). Data files are released for verification and
reproduction of the paper's results.
