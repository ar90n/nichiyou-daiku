"""pytest plugin: record every source parse_dsl is given, for the Rust corpus.

ND_CAPTURE=FILE names the JSON-lines file to append to.
"""

import json
import os

from nichiyou_daiku.dsl.parser import DSLParser

_original_parse = DSLParser.parse


def _recording_parse(self, dsl_string):
    path = os.environ.get("ND_CAPTURE")
    if path and isinstance(dsl_string, str):
        with open(path, "a", encoding="utf-8") as out:
            out.write(json.dumps(dsl_string, ensure_ascii=False) + "\n")
    return _original_parse(self, dsl_string)


DSLParser.parse = _recording_parse
