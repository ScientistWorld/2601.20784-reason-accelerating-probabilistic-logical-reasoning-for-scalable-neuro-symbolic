# Scientist Constraints

## Interface

A method is a procedure registered by a manifest in `checkpoints/` and invoked as `<command> --instance IN.json --out OUT.json`.  It may use the instance's model, calibration data and budgets, and any public code or data in the repository.  It must not read evaluator files under `eval/` or the held-out samples of any instance.

## Data

Develop on the public instances in `data/reason_benchmarks.json` (train slice).  The hidden test instances come from the same generating process with different seeds.  Do not hard-code outputs for specific instances: test instances are new.

## Evaluation

Use `scripts/evaluate_train.sh` / `scripts/evaluate.sh` unchanged.  All scored quantities (memory, equivalence, normalisation, likelihood) are recomputed by the evaluator from the returned models; self-reported numbers are ignored.

## Resource Accounting

Memory is nodes + edges of the evaluator-compiled two-input DAG.  Budgets are fixed by the evaluator.  No metric depends on wall-clock time; each call is limited to 30 minutes.

## Problem Scope

Outputs must stay in the kernel's model class: an equivalent CNF over the same variables; an HMM over the same observation alphabet; a smooth, decomposable circuit with Bernoulli leaves over the same variables.  Any restructuring inside the class (removing, merging or re-parameterising structure) is allowed.

## Compliance Checklist

- [ ] Method registered via a manifest; scored with the unchanged evaluate scripts.
- [ ] Every model fits its budget and is valid (equivalent / normalised / smooth and decomposable).
- [ ] No use of held-out samples or evaluator files.
- [ ] No instance-specific hard-coding.
