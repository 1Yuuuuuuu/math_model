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


def _seed_kwargs(seed: int | None, params: dict[str, Any]) -> dict[str, Any]:
    kwargs = dict(params)
    if seed is not None:
        if "random_state" in kwargs:
            raise ValueError("conflict: both seed and random_state provided")
        kwargs["random_state"] = seed
    return kwargs


def _register_builtins() -> None:
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeClassifier

    def _linear(seed: int | None, params: dict[str, Any]) -> Any:
        return LinearRegression(**dict(params))

    def _tree(seed: int | None, params: dict[str, Any]) -> Any:
        return DecisionTreeClassifier(**_seed_kwargs(seed, params))

    def _kmeans(seed: int | None, params: dict[str, Any]) -> Any:
        kwargs = _seed_kwargs(seed, params)
        kwargs.setdefault("n_clusters", 3)
        return KMeans(**kwargs)

    register_model("linear-regression", _linear)
    register_model("decision-tree", _tree)
    register_model("kmeans", _kmeans)


_register_builtins()
