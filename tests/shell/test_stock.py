"""Stock lengths and saw kerf from a store's TOML file."""

import re

import pytest

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.shell.cutting import DEFAULT_KERF_MM, DEFAULT_STANDARD_LENGTHS
from nichiyou_daiku.shell.stock import Stock, StockFileError, load_stock


def _write(tmp_path, text):
    path = tmp_path / "stock.toml"
    path.write_text(text)
    return path


def test_listed_types_replace_the_defaults_and_the_rest_keep_them(tmp_path):
    stock = load_stock(
        _write(tmp_path, 'kerf = 2\n[lengths]\n"2x4" = [1820, 2440]\n"1x4" = [910]\n')
    )
    assert stock.kerf == 2.0
    assert stock.lengths[PieceType.PT_2x4] == [1820.0, 2440.0]
    assert stock.lengths[PieceType.PT_1x4] == [910.0]
    assert stock.lengths[PieceType.PT_2x2] == DEFAULT_STANDARD_LENGTHS[PieceType.PT_2x2]


def test_kerf_and_lengths_are_optional(tmp_path):
    assert load_stock(_write(tmp_path, "")) == Stock(
        lengths=DEFAULT_STANDARD_LENGTHS, kerf=DEFAULT_KERF_MM
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("kerf = \n", "not valid TOML"),
        ('[lenghts]\n"2x4" = [1820]\n', "Unknown key 'lenghts'"),
        ("lengths = [1820]\n", "[lengths] must be a table"),
        ('[lengths]\n"2x5" = [1820]\n', "Unknown lumber type '2x5'"),
        ('[lengths]\n"2x4" = "1820"\n', "'2x4' must be a list of lengths"),
        ('[lengths]\n"2x4" = []\n', "'2x4' needs at least one length"),
        ('[lengths]\n"2x4" = [1820, 0]\n', "'2x4' lengths must be positive"),
        ('[lengths]\n"2x4" = [true]\n', "'2x4' lengths must be positive"),
        ('kerf = "3"\n', "kerf must be a number"),
        ("kerf = -1\n", "kerf must be 0 or more"),
    ],
)
def test_mistakes_say_what_is_wrong(tmp_path, text, message):
    with pytest.raises(StockFileError, match=re.escape(message)):
        load_stock(_write(tmp_path, text))


def test_an_unknown_type_lists_the_known_ones(tmp_path):
    with pytest.raises(StockFileError) as error:
        load_stock(_write(tmp_path, '[lengths]\n"2x5" = [1820]\n'))
    assert ", ".join(t.value for t in PieceType) in str(error.value)


def test_a_missing_file_is_explained(tmp_path):
    with pytest.raises(StockFileError, match="Cannot read the stock file"):
        load_stock(tmp_path / "missing.toml")
