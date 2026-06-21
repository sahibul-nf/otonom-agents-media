"""HyperFrames per-template recipe registry."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

from ._base import LayoutContext, RecipeStyleMeta, TemplateRecipe
from ._catalog import get_builtin_recipe

if TYPE_CHECKING:
    pass

_REGISTRY: dict[str, TemplateRecipe] = {}


def _discover_modules() -> None:
    package = importlib.import_module(__name__)
    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        name = module_info.name
        if name.rsplit(".", 1)[-1].startswith("_"):
            continue
        module = importlib.import_module(name)
        recipe = getattr(module, "recipe", None)
        if recipe is not None:
            _REGISTRY[recipe.template_id] = recipe


def get_recipe(template_id: str) -> TemplateRecipe:
    if not _REGISTRY:
        _discover_modules()
    recipe = _REGISTRY.get(template_id)
    if recipe is None:
        recipe = get_builtin_recipe(template_id)
        _REGISTRY[template_id] = recipe
    return recipe


def recipe_style_meta(template_id: str) -> RecipeStyleMeta:
    return get_recipe(template_id).style_meta()


__all__ = [
    "LayoutContext",
    "RecipeStyleMeta",
    "TemplateRecipe",
    "get_builtin_recipe",
    "get_recipe",
    "recipe_style_meta",
]
