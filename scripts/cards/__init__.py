"""The card modules: each draws one lane of the profile's SVG cards with kit.py.

Every module in this package exposes render(data, ctx) -> {file name: svg text}
and is pure: no files, no network, no clock (the day is ctx["today"]).
render-svgs.py writes what they return; preview.py renders one of them into
.scratch/preview/ without touching assets/.
"""

# The order render-svgs.py runs them in; a file may be drawn by one module only.
# stack.svg and ai-stack.svg have no module yet: they are kept as committed.
MODULES = (
    "hero",
    "chrome",
    "career",
    "samples",
    "projects",
    "oss",
    "tools",
    "stats",
)
