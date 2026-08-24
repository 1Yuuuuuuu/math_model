from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_model(name: str, factory: Callable[..., Any]) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("model name must be a non-empty string")
    _REGISTRY[name] = factory


def list_models() -> list[str]:
    return sorted(_REGISTRY)


def get_model(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"unknown model: {name}")
    return _REGISTRY[name]


def _seed_kwargs(seed: int | None) -> dict[str, int]:
    return {"random_state": seed} if seed is not None else {}


def _register_builtins() -> None:
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeClassifier

    register_model("linear-regression", lambda **kw: LinearRegression())
    register_model("decision-tree", lambda **kw: DecisionTreeClassifier(**_seed_kwargs(kw.get("seed"))))
    register_model("kmeans", lambda **kw: KMeans(n_clusters=kw.get("n_clusters", 3), **_seed_kwargs(kw.get("seed"))))


_register_builtins()
