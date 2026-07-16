"""One filesystem-object identity policy for current SkillGuard paths."""

from __future__ import annotations

import os
from pathlib import Path


def canonical_filesystem_path(path: str | Path) -> Path:
    """Canonicalize the deepest existing ancestor and preserve a missing suffix.

    Windows may expose one object through both an 8.3 short name and its long
    name.  All identity and containment checks use the long physical spelling;
    callers that must inspect a final link use :func:`lexical_filesystem_path`.
    """

    absolute = Path(os.path.abspath(path))
    missing_parts: list[str] = []
    existing = absolute
    while not os.path.lexists(existing):
        if existing == existing.parent:
            raise FileNotFoundError(str(absolute))
        missing_parts.append(existing.name)
        existing = existing.parent
    resolved = existing.resolve(strict=True)
    if os.name == "nt":
        try:
            import ctypes

            get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW
            required = get_long_path_name(str(resolved), None, 0)
            if required:
                buffer = ctypes.create_unicode_buffer(required)
                written = get_long_path_name(str(resolved), buffer, required)
                if written and written < required:
                    resolved = Path(buffer.value)
        except (AttributeError, OSError, ValueError):
            pass
    return resolved.joinpath(*reversed(missing_parts))


def lexical_filesystem_path(path: str | Path) -> Path:
    """Canonicalize the parent identity without following the final component."""

    absolute = Path(os.path.abspath(path))
    return canonical_filesystem_path(absolute.parent) / absolute.name


def physical_relative_path(
    path: str | Path,
    root: str | Path,
    *,
    preserve_final_component: bool = False,
) -> Path:
    """Return a relative token after canonical physical containment checks."""

    canonical_root = canonical_filesystem_path(root)
    canonical_path = (
        lexical_filesystem_path(path)
        if preserve_final_component
        else canonical_filesystem_path(path)
    )
    return canonical_path.relative_to(canonical_root)


def same_filesystem_object(left: str | Path, right: str | Path) -> bool:
    """Compare object identity, not user-visible path spelling."""

    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, OSError):
        return canonical_filesystem_path(left) == canonical_filesystem_path(right)


__all__ = [
    "canonical_filesystem_path",
    "lexical_filesystem_path",
    "physical_relative_path",
    "same_filesystem_object",
]
