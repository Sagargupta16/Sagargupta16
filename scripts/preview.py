"""Render one card module offline into .scratch/preview/<module>/, or dump the card context.

    python scripts/preview.py <module>   every file cards/<module>.py returns, with its bytes
    python scripts/preview.py --ctx      the context as JSON, in .scratch/preview/ctx.json

Nothing under assets/ is written, and nothing is fetched: the data is the
checked-in snapshot, loaded by the same code render-svgs.py runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parent
PREVIEW = SCRIPTS.parent / ".scratch" / "preview"


def load_renderer() -> ModuleType:
    """Import render-svgs.py by path (its name has a dash) with the network switched off."""
    spec = importlib.util.spec_from_file_location(
        "render_svgs", SCRIPTS / "render-svgs.py"
    )
    renderer = importlib.util.module_from_spec(spec)
    sys.modules["render_svgs"] = renderer
    spec.loader.exec_module(renderer)
    renderer.OFFLINE = True
    return renderer


def _printable(value: object) -> object:
    """Shorten embedded images so the dump stays readable; everything else is kept whole."""
    if isinstance(value, str) and value.startswith("data:"):
        return f"{value[:40]}... ({len(value):,} characters)"
    if isinstance(value, dict):
        return {key: _printable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_printable(item) for item in value]
    return value


def dump_context(ctx: dict) -> int:
    plain = {
        key: _printable(value) for key, value in ctx.items() if not callable(value)
    }
    PREVIEW.mkdir(parents=True, exist_ok=True)
    path = PREVIEW / "ctx.json"
    path.write_text(json.dumps(plain, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path} ({len(plain)} keys; callables left out)")
    for key in plain:
        print(f"  {key}")
    return 0


def preview_module(renderer: ModuleType, name: str, data: dict, ctx: dict) -> int:
    files = renderer.render_module(name, data, ctx)  # raises on a bad file name
    if files is None:
        return 1  # render_module printed "missing module <name>"
    out = PREVIEW / name
    out.mkdir(parents=True, exist_ok=True)
    status = 0
    for file, svg in files.items():
        (out / file).write_text(svg, encoding="utf-8", newline="\n")
        try:
            ET.fromstring(svg)  # nosec B314 - our own output
        except ET.ParseError as error:
            print(f"{file}: invalid XML: {error}")
            status = 1
            continue
        print(f"{file}  {len(svg.encode('utf-8')):,} bytes")
    print(f"{len(files)} files in {out}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("module", nargs="?", help="a name from cards.MODULES")
    parser.add_argument("--ctx", action="store_true", help="write the context as JSON")
    args = parser.parse_args()
    if not args.ctx and not args.module:
        parser.error("name a module or pass --ctx")
    renderer = load_renderer()
    data = renderer.load_data()
    ctx = renderer.build_context(data)
    if args.ctx:
        return dump_context(ctx)
    return preview_module(renderer, args.module, data, ctx)


if __name__ == "__main__":
    sys.exit(main())
