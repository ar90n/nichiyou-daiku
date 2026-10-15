"""Stock board lengths and saw kerf for a store, read from a TOML file.

::

    kerf = 2                         # saw kerf in mm (3 when left out)

    [lengths]                        # lengths in mm; unlisted types keep the defaults
    "2x4" = [1820, 2440, 3050, 3650]
    "1x4" = [910, 1820]
"""

import tomllib
from os import PathLike
from pathlib import Path

from pydantic import BaseModel

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.shell.cutting import DEFAULT_KERF_MM, DEFAULT_STANDARD_LENGTHS

_KEYS = ("kerf", "lengths")


class StockFileError(ValueError):
    """A stock file that cannot be read or does not follow the format."""


class Stock(BaseModel, frozen=True):
    """The board lengths a store sells per lumber type, and the saw kerf."""

    lengths: dict[PieceType, list[float]]
    kerf: float


def _is_number(value: object) -> bool:
    # TOML booleans are Python ints; a length of `true` is a mistake
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _lengths(path: Path, table: object) -> dict[PieceType, list[float]]:
    if not isinstance(table, dict):
        raise StockFileError(
            f'{path}: [lengths] must be a table of lumber types, e.g. "2x4" = [1820, 2440]'
        )
    known = {piece_type.value: piece_type for piece_type in PieceType}
    lengths = dict(DEFAULT_STANDARD_LENGTHS)
    for name, values in table.items():
        if name not in known:
            raise StockFileError(
                f"{path}: Unknown lumber type '{name}' in [lengths]. "
                f"Use one of: {', '.join(known)}"
            )
        if not isinstance(values, list):
            raise StockFileError(
                f"{path}: '{name}' must be a list of lengths in mm, "
                f'e.g. "{name}" = [1820, 2440]'
            )
        if not values:
            raise StockFileError(
                f"{path}: '{name}' needs at least one length, e.g. \"{name}\" = [1820]"
            )
        if not all(_is_number(value) and value > 0 for value in values):
            raise StockFileError(
                f"{path}: '{name}' lengths must be positive numbers in mm, got {values}"
            )
        lengths[known[name]] = [float(value) for value in values]
    return lengths


def load_stock(path: str | PathLike[str]) -> Stock:
    """Read a stock file; lumber types it leaves out keep the default lengths.

    Raises:
        StockFileError: What is wrong with the file and how to fix it
    """
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise StockFileError(
            f"Cannot read the stock file {path}: {e.strerror or e}"
        ) from e
    except tomllib.TOMLDecodeError as e:
        raise StockFileError(
            f'{path}: not valid TOML ({e}). Write e.g. kerf = 3 and "2x4" = [1820, 2440]'
        ) from e

    for key in data:
        if key not in _KEYS:
            raise StockFileError(
                f"{path}: Unknown key '{key}'. Use 'kerf' and a [lengths] table"
            )

    kerf = data.get("kerf", DEFAULT_KERF_MM)
    if not _is_number(kerf):
        raise StockFileError(f"{path}: kerf must be a number in mm, got {kerf!r}")
    if kerf < 0:
        raise StockFileError(f"{path}: kerf must be 0 or more, got {kerf}")

    return Stock(lengths=_lengths(path, data.get("lengths", {})), kerf=float(kerf))
