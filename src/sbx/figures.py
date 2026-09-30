"""Рисунки для отчёта: python -m sbx.figures --config configs/default.yaml"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from . import viz


def main(cfg_path: str):
    cfg = yaml.safe_load(open(cfg_path))
    res = Path(cfg["paths"]["results"])
    fig = Path(cfg["paths"]["figures"]); fig.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_load(open("configs/cluster_names.yaml", encoding="utf-8"))
    names = {int(k): v["short"] for k, v in meta["clusters"].items()}
    months = pd.read_csv(res / "final_labels.csv", index_col=0).columns.tolist()
    viz.k_selection(res, fig)
    viz.edge_rules(res, fig)
    viz.methods(res, fig)
    viz.cluster_map(res, fig, Path(cfg["paths"]["raw"]), names)
    viz.dna(res, fig, names, meta["meta"]["dna_features"], meta["meta"]["feature_ru"])
    viz.dynamics(res, fig, names, months)
    print("рисунки:", sorted(p.name for p in fig.glob("*.png")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    main(ap.parse_args().config)
