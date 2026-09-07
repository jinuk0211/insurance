"""Entry point for verified three-role preprocessing refinement.

The former Claude/stub driver is preserved under
research/harness_v3/legacy_outer_loop_20260907/evolve.py.
Stage-2/3 refinement is not implemented by this Stage-1 entry point.
"""
from scripts_evolve.refinement_loop import main


if __name__ == "__main__":
    raise SystemExit(main())
