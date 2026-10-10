# FactoryPulse ML Package

Shared data schemas, feature transforms, predictive-maintenance models,
training entry points, and evaluation utilities for FactoryPulse.

## Development install

From the repository root, install the package into the active Python
environment:

```bash
python -m pip install -e ./ml
```

Data preparation and training stages are configured in the root `dvc.yaml` and
`params.yaml` files. Public source data belongs under `data/raw/`; generated
intermediate and processed data is tracked by DVC.
