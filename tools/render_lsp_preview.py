#!/usr/bin/env python3
"""Headless point-for-point replay of the supplied legacy AutoLISP.

This intentionally implements only the small AutoLISP/CAD subset used by
0930-16.LSP.  It preserves the program's coordinate calculations and LINE
emission while treating view/edit commands that do not change visible line
endpoints as no-ops.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class Sym(str):
    pass


@dataclass
class Pair:
    car: Any
    cdr: Any


@dataclass
class Quote:
    value: Any


def tokenize(source: str) -> list[str]:
    out, i, n = [], 0, len(source)
    while i < n:
        c = source[i]
        if c.isspace():
            i += 1
        elif c == ";":
            while i < n and source[i] not in "\r\n":
                i += 1
        elif c in "()'":
            out.append(c)
            i += 1
        elif c == '"':
            i += 1
            buf = []
            while i < n and source[i] != '"':
                if source[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(source[i])
                i += 1
            i += 1
            out.append('"' + "".join(buf) + '"')
        else:
            j = i
            while j < n and not source[j].isspace() and source[j] not in "()';\"":
                j += 1
            out.append(source[i:j])
            i = j
    return out


def atom(token: str) -> Any:
    if token.startswith('"'):
        return token[1:-1]
    try:
        return float(token) if any(ch in token for ch in ".eE") else int(token)
    except ValueError:
        return Sym(token.upper())


def parse_all(tokens: list[str]) -> list[Any]:
    pos = 0

    def parse() -> Any:
        nonlocal pos
        token = tokens[pos]
        pos += 1
        if token == "'":
            return Quote(parse())
        if token != "(":
            return atom(token)
        items = []
        while tokens[pos] != ")":
            if tokens[pos] == ".":
                pos += 1
                tail = parse()
                if tokens[pos] != ")" or len(items) != 1:
                    raise SyntaxError("unsupported dotted list")
                pos += 1
                return Pair(items[0], tail)
            items.append(parse())
        pos += 1
        return items

    forms = []
    while pos < len(tokens):
        forms.append(parse())
    return forms


class Env(dict):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

    def lookup(self, key: Sym):
        if key in self:
            return self[key]
        if self.parent is not None:
            return self.parent.lookup(key)
        return None

    def assign(self, key: Sym, value: Any):
        env = self
        while env is not None:
            if key in env:
                env[key] = value
                return value
            env = env.parent
        self[key] = value
        return value


@dataclass
class Function:
    params: list[Sym]
    locals: list[Sym]
    body: list[Any]


class Replay:
    def __init__(self):
        self.global_env = Env()
        self.functions: dict[Sym, Function] = {}
        self.layers: dict[str, int] = {"0": 7}
        self.current_layer = "0"
        self.lines: list[dict[str, Any]] = []
        self.distances = iter([1.0, 0.6, 5.0, 5.0, 0.1, 0.8])
        self.integers = iter([10, 6])
        # Only X is consumed by the legacy pin-center prompts.  The third
        # point is a pause and its coordinates are ignored by the LSP.
        self.points = iter([[-8.0, 0.0], [8.0, 0.0], [0.0, 0.0]])
        self.vars = {"CLAYER": "0", "CDATE": 20210930.0, "OSNAPCOORD": 2}
        self._install_builtins()

    @staticmethod
    def truth(value):
        return value is not None and value is not False

    def _install_builtins(self):
        e = self.global_env
        e[Sym("NIL")] = None
        e[Sym("T")] = True
        e.update({
            Sym("+"): lambda *a: sum(a),
            Sym("-"): lambda a, *b: -a if not b else a - sum(b),
            Sym("*"): lambda *a: math.prod(a),
            Sym("/"): lambda a, *b: (1.0 / a) if not b else _divide(a, b),
            Sym("ABS"): abs,
            Sym("SIN"): math.sin,
            Sym("COS"): math.cos,
            Sym("ATAN"): lambda a, *b: math.atan(a) if not b else math.atan2(a, b[0]),
            Sym("REM"): lambda a, b: a % b,
            Sym("1+"): lambda a: a + 1,
            Sym("1-"): lambda a: a - 1,
            Sym("="): lambda a, b: a == b,
            Sym("/="): lambda a, b: a != b,
            Sym("<"): lambda a, b: a < b,
            Sym(">"): lambda a, b: a > b,
            Sym("<="): lambda a, b: a <= b,
            Sym(">="): lambda a, b: a >= b,
            Sym("LIST"): lambda *a: list(a),
            Sym("CONS"): lambda a, b: [a] if b is None else (([a] + b) if isinstance(b, list) else Pair(a, b)),
            Sym("CAR"): lambda a: a.car if isinstance(a, Pair) else a[0],
            Sym("CDR"): lambda a: a.cdr if isinstance(a, Pair) else a[1:],
            Sym("CADR"): lambda a: a[1],
            Sym("NTH"): lambda n, a: a[int(n)],
            Sym("LENGTH"): len,
            Sym("DISTANCE"): lambda a, b: math.dist(a[:2], b[:2]),
            Sym("STRCAT"): lambda *a: "".join(str(x) for x in a),
            Sym("ITOA"): lambda value: str(int(value)),
            Sym("INITGET"): lambda *_: None,
            Sym("ASCII"): lambda s: ord(s[0]),
            Sym("NOT"): lambda value: None if self.truth(value) else True,
            Sym("STRCASE"): lambda value: str(value).upper(),
            Sym("WCMATCH"): lambda *_: None,
            Sym("PROMPT"): lambda *_: None,
            Sym("COMMAND-S"): lambda *_: None,
            Sym("SUBSTR"): lambda s, start, *ln: s[int(start)-1:] if not ln else s[int(start)-1:int(start)-1+int(ln[0])],
            Sym("RTOS"): lambda value, *_: f"{value:.4f}",
            Sym("VL-LOAD-COM"): lambda: None,
            Sym("PRINC"): lambda *_: None,
            Sym("GETDIST"): lambda *_: next(self.distances),
            Sym("GETINT"): lambda *_: next(self.integers),
            Sym("GETPOINT"): lambda *_: next(self.points),
            Sym("GETVAR"): self.getvar,
            Sym("SETVAR"): self.setvar,
            Sym("TBLSEARCH"): lambda table, name: name if str(name) in self.layers else None,
            Sym("ENTMAKE"): self.entmake,
            Sym("ENTMAKEX"): self.entmake,
            Sym("VL-CMDF"): self.vl_cmdf,
            Sym("SSGET"): self.ssget,
        })

    def getvar(self, name):
        return self.vars.get(str(name).upper(), 0)

    def setvar(self, name, value):
        self.vars[str(name).upper()] = value
        if str(name).upper() == "CLAYER":
            self.current_layer = str(value)
        return value

    @staticmethod
    def pairs(data):
        result = []
        for item in data:
            if isinstance(item, Pair):
                result.append(item)
            elif isinstance(item, list) and len(item) >= 2 and isinstance(item[0], (int, float)):
                result.append(Pair(item[0], item[1:] if len(item) > 2 else item[1]))
        return result

    def entmake(self, data):
        fields = self.pairs(data)
        kind = next((p.cdr for p in fields if p.car == 0), None)
        if str(kind).upper() == "LAYER":
            name = next((p.cdr for p in fields if p.car == 2), None)
            color = next((p.cdr for p in fields if p.car == 62), 7)
            if name is not None:
                self.layers.setdefault(str(name), int(color))
            return data
        if str(kind).upper() == "LINE":
            start = next((p.cdr for p in fields if p.car == 10), None)
            end = next((p.cdr for p in fields if p.car == 11), None)
            layer = next((p.cdr for p in fields if p.car == 8), self.current_layer)
            if start is not None and end is not None:
                self.add_line(start, end, str(layer))
            return data
        return data

    def add_line(self, start, end, layer=None):
        if start is None or end is None:
            return
        self.lines.append({"a": [float(start[0]), float(start[1])],
                           "b": [float(end[0]), float(end[1])],
                           "layer": layer or self.current_layer})

    def ssget(self, *_args):
        return [i for i, line in enumerate(self.lines) if line["layer"].lower() == "cache"]

    def vl_cmdf(self, *args):
        if not args:
            return None
        command = str(args[0]).lstrip("_").upper()
        if command == "LAYER":
            words = [str(x).lstrip("_") for x in args[1:]]
            if words and words[0].upper() in {"S", "SET"} and len(words) > 1:
                self.current_layer = words[1]
                self.vars["CLAYER"] = words[1]
            elif words and words[0].upper() in {"N", "NEW"} and len(words) > 1:
                self.layers.setdefault(words[1], 7)
            return None
        if command == "LINE":
            points = [x for x in args[1:] if isinstance(x, list) and len(x) >= 2]
            for a, b in zip(points, points[1:]):
                self.add_line(a, b)
            return None
        if command == "CHANGE":
            selection = args[1] if len(args) > 1 and isinstance(args[1], list) else []
            words = [str(x) for x in args]
            for i, word in enumerate(words[:-1]):
                if word.upper() == "LA":
                    for index in selection:
                        self.lines[index]["layer"] = words[i + 1]
                    break
            return None
        # PEDIT/JOIN preserves the visible segment geometry. ZOOM is view-only.
        # FILLET R0 and CHAMFER affect only the final meeting endpoints and are
        # audited separately after point replay.
        return None

    def eval(self, form, env=None):
        env = env or self.global_env
        if isinstance(form, Quote):
            return form.value
        if isinstance(form, Sym):
            return env.lookup(form)
        if not isinstance(form, list):
            return form
        if not form:
            return None
        head = form[0]
        if head == Sym("QUOTE"):
            return form[1]
        if head == Sym("SETQ"):
            result = None
            for i in range(1, len(form), 2):
                result = self.eval(form[i + 1], env)
                env.assign(form[i], result)
            return result
        if head == Sym("IF"):
            branch = form[2] if self.truth(self.eval(form[1], env)) else (form[3] if len(form) > 3 else None)
            return self.eval(branch, env) if branch is not None else None
        if head == Sym("PROGN"):
            return self.eval_sequence(form[1:], env)
        if head == Sym("WHILE"):
            result = None
            guard = 0
            while self.truth(self.eval(form[1], env)):
                result = self.eval_sequence(form[2:], env)
                guard += 1
                if guard > 100000:
                    raise RuntimeError("while-loop guard exceeded")
            return result
        if head == Sym("REPEAT"):
            count = int(self.eval(form[1], env))
            result = None
            for _ in range(max(0, count)):
                result = self.eval_sequence(form[2:], env)
            return result
        if head == Sym("AND"):
            result = True
            for item in form[1:]:
                result = self.eval(item, env)
                if not self.truth(result):
                    return None
            return result
        if head == Sym("OR"):
            for item in form[1:]:
                result = self.eval(item, env)
                if self.truth(result):
                    return result
            return None
        if head == Sym("DEFUN"):
            name, signature = form[1], form[2]
            if Sym("/") in signature:
                split = signature.index(Sym("/"))
                params, locals_ = signature[:split], signature[split + 1:]
            else:
                params, locals_ = signature, []
            self.functions[name] = Function(params, locals_, form[3:])
            return name

        args = [self.eval(item, env) for item in form[1:]]
        if isinstance(head, Sym) and head in self.functions:
            fn = self.functions[head]
            local = Env(env)
            for name, value in zip(fn.params, args):
                local[name] = value
            for name in fn.locals:
                local[name] = None
            return self.eval_sequence(fn.body, local)
        function = env.lookup(head) if isinstance(head, Sym) else self.eval(head, env)
        if not callable(function):
            raise RuntimeError(f"unknown function: {head}")
        return function(*args)

    def eval_sequence(self, forms, env):
        result = None
        for form in forms:
            result = self.eval(form, env)
        return result

    def load_and_run(self, source: Path):
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("big5")
        forms = parse_all(tokenize(text))
        self.eval_sequence(forms, self.global_env)
        command = Sym("C:PCAPSENSOR") if Sym("C:PCAPSENSOR") in self.functions else Sym("C:ASENSOR")
        self.eval([command], self.global_env)


def _divide(a, rest):
    result = float(a)
    for value in rest:
        result /= value
    return result


def dxf_text(replay: Replay) -> str:
    chunks = ["0", "SECTION", "2", "HEADER", "0", "ENDSEC", "0", "SECTION", "2", "TABLES",
              "0", "TABLE", "2", "LAYER", "70", str(len(replay.layers))]
    for name, color in replay.layers.items():
        chunks += ["0", "LAYER", "2", name, "70", "0", "62", str(color), "6", "CONTINUOUS"]
    chunks += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for line in replay.lines:
        chunks += ["0", "LINE", "8", line["layer"], "10", f"{line['a'][0]:.8f}",
                   "20", f"{line['a'][1]:.8f}", "30", "0.0", "11", f"{line['b'][0]:.8f}",
                   "21", f"{line['b'][1]:.8f}", "31", "0.0"]
    chunks += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(chunks) + "\n"


COLORS = {
    "Top ITO": "#ffd447", "Top Ag": "#ff8a3d", "Top laser": "#ff4057",
    "Bottom ITO": "#35a7ff", "Bottom Ag": "#b875ff", "Bottom laser": "#31e6d3",
    "0": "#7f919c", "cache": "#ffffff",
}


def render_png(replay: Replay, output: Path, label: str, allowed_layers=None):
    visible = [line for line in replay.lines
               if line["layer"].lower() != "cache"
               and (allowed_layers is None or line["layer"] in allowed_layers)]
    xs = [p for line in visible for p in (line["a"][0], line["b"][0])]
    ys = [p for line in visible for p in (line["a"][1], line["b"][1])]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    height, margin = 1400, 75
    aspect = (max_x - min_x) / max(1e-9, max_y - min_y)
    width = max(720, min(1800, int((height - 2 * margin) * aspect + 2 * margin)))
    scale = min((width - 2 * margin) / max(1e-9, max_x - min_x),
                (height - 2 * margin) / max(1e-9, max_y - min_y))

    def xy(point):
        return (margin + (point[0] - min_x) * scale,
                height - margin - (point[1] - min_y) * scale)

    image = Image.new("RGB", (width, height), "#101820")
    draw = ImageDraw.Draw(image)
    for x in range(0, width, 25):
        draw.line([(x, 0), (x, height)], fill="#22313b")
    for y in range(0, height, 25):
        draw.line([(0, y), (width, y)], fill="#22313b")
    for line in visible:
        draw.line([xy(line["a"]), xy(line["b"])], fill=COLORS.get(line["layer"], "#dbe7ee"), width=2)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 22) if Path(font_path).exists() else ImageFont.load_default()
    draw.text((35, 25), f"{label} point replay — {len(visible)} visible LINE entities",
              fill="#dbe7ee", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


def main():
    root = Path(__file__).resolve().parents[1]
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "pcap-diamond-generator.lsp"
    replay = Replay()
    replay.load_and_run(source)
    stem = "pcap-sensor-corrected-preview" if source.name == "pcap-diamond-generator.lsp" else f"{source.stem}-point-replay"
    dxf = root / f"{stem}.dxf"
    png = root / f"{stem}.png"
    dxf.write_text(dxf_text(replay), encoding="ascii")
    render_png(replay, png, source.name)
    if source.name == "pcap-diamond-generator.lsp":
        render_png(replay, root / "pcap-sensor-electrodes-preview.png", source.name,
                   {"Top ITO", "Bottom ITO"})
        render_png(replay, root / "pcap-sensor-ag-routing-preview.png", source.name,
                   {"Top Ag", "Bottom Ag"})
        render_png(replay, root / "pcap-sensor-laser-preview.png", source.name,
                   {"Top laser", "Bottom laser"})
    counts = {}
    for line in replay.lines:
        counts[line["layer"]] = counts.get(line["layer"], 0) + 1
    print(dxf)
    print(png)
    print(counts)


if __name__ == "__main__":
    main()
