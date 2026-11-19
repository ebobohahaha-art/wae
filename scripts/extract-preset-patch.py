"""Extract Codex's design assets from the supplied git-format patch.

The upstream base stylesheet is checked by its git blob hash before applying
any hunks. This is an asset extraction utility, not a deploy step.
"""
from pathlib import Path
from urllib.request import urlopen
import base64
import hashlib
import re
import zlib

root = Path(__file__).resolve().parent.parent
public = root / "public"
patch = (public / "apiduh-preset-gears.patch").read_text(encoding="utf-8").splitlines(keepends=True)


def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


sections = {}
for index, line in enumerate(patch):
    if line.startswith("diff --git a/"):
        name = line.split(" b/", 1)[1].strip()
        end = next((i for i in range(index + 1, len(patch))
                    if patch[i].startswith("diff --git a/")), len(patch))
        sections[name] = patch[index:end]


def apply_hunks(source, section):
    old = source.splitlines(keepends=True)
    result = []
    position = 0
    index = 0
    while index < len(section):
        match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", section[index])
        if not match:
            index += 1
            continue
        start = max(0, int(match[1]) - 1)
        assert position <= start
        result.extend(old[position:start])
        position = start
        index += 1
        while (index < len(section) and section[index][:1] in " +-\\" and
               not section[index].startswith(("--- ", "+++ ", "-- "))):
            line = section[index]
            if line.startswith(" "):
                assert position < len(old) and old[position] == line[1:], f"Context at {position + 1}"
                result.append(old[position])
                position += 1
            elif line.startswith("-"):
                assert position < len(old) and old[position] == line[1:], f"Deletion at {position + 1}"
                position += 1
            elif line.startswith("+"):
                result.append(line[1:])
            index += 1
    result.extend(old[position:])
    return "".join(result).encode("utf-8")


base = urlopen(
    "https://raw.githubusercontent.com/ffsumi31-byte/neonAPI/main/public/style.css",
    timeout=20,
).read()
assert blob_hash(base).startswith("c3990c0"), "Upstream base stylesheet changed"
style = apply_hunks(base.decode("utf-8"), sections["public/style.css"])
gears = apply_hunks("", sections["public/preset-gears.js"])
license_text = apply_hunks("", sections["public/fonts/bricolage-grotesque-OFL.txt"])
assert blob_hash(style).startswith("b4ec77e")
assert blob_hash(gears).startswith("6a94ada")

font_section = sections["public/fonts/bricolage-grotesque.woff2"]
start = font_section.index("literal 41344\n") + 1
packed = b""
for line in font_section[start:]:
    if not line.strip():
        break
    length = ord(line[0]) - ord("A") + 1 if line[0].isupper() else ord(line[0]) - ord("a") + 27
    packed += base64.b85decode(line[1:].strip().encode())[:length]
font = zlib.decompress(packed)
assert len(font) == 41344
assert blob_hash(font) == "82152a40802e0646b7a732744394a02c8c72772f"

(public / "fonts").mkdir(exist_ok=True)
for name, data in (
    ("codex-theme.css", style),
    ("preset-gears.js", gears),
    ("fonts/bricolage-grotesque-OFL.txt", license_text),
    ("fonts/bricolage-grotesque.woff2", font),
):
    (public / name).write_bytes(data)
    print(name, len(data), blob_hash(data))
