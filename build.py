#!/usr/bin/env python3
"""
Rebuild the Ghost Byte site from the source OTF.

    python3 build.py path/to/GhostByte-Regular.otf

Generates fonts/{otf,ttf,woff2,woff}, the download zip, and index.html with the
woff2 embedded plus every file size and character count read from the font
itself. Re-run this after editing the font's name table.

Needs: pip install fonttools brotli
"""
import base64, json, os, re, shutil, sys, unicodedata, zipfile

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(ROOT, "fonts")
TEMPLATE = os.path.join(ROOT, "index.template.html")
VERSION = "1.000"


def build_ttf(src, dest):
    """CFF outlines -> quadratic TrueType outlines."""
    f = TTFont(src)
    gs = f.getGlyphSet()
    glyf = table__g_l_y_f()
    glyf.glyphs, glyf.glyphOrder = {}, f.getGlyphOrder()
    for name in f.getGlyphOrder():
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        g = pen.glyph()
        g.recalcBounds(glyf)
        glyf.glyphs[name] = g
    f["glyf"] = glyf
    f["loca"] = newTable("loca")

    maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    defaults = dict(
        maxZones=1, maxTwilightPoints=0, maxStorage=0, maxFunctionDefs=0,
        maxInstructionDefs=0, maxStackElements=0, maxSizeOfInstructions=0,
        maxComponentElements=0, maxComponentDepth=0, maxPoints=0,
        maxContours=0, maxCompositePoints=0, maxCompositeContours=0,
        numGlyphs=len(glyf.glyphs),
    )
    for k, v in defaults.items():
        setattr(maxp, k, v)
    f["maxp"] = maxp
    maxp.recalc(f)

    del f["CFF "]
    f["head"].indexToLocFormat = 0
    f["post"].formatType = 2.0
    f["post"].extraNames, f["post"].mapping = [], {}
    f["post"].glyphOrder = f.getGlyphOrder()
    f.sfntVersion = "\x00\x01\x00\x00"
    f.save(dest)


def group_of(cp, ch, cat):
    if 0x41 <= cp <= 0x5A:
        return "Uppercase"
    if 0x61 <= cp <= 0x7A:
        return "Lowercase"
    if cp == 0x20:
        return "Punctuation"
    if cat == "Nd" or 0x2070 <= cp <= 0x2089 or 0x215B <= cp <= 0x215E:
        return "Numerals & fractions"
    if cat == "Mn":
        return "Combining marks"
    if cat == "Sc":
        return "Currency"
    if 0x2190 <= cp <= 0x21FF:
        return "Arrows"
    if cat.startswith("L"):
        return "Accented letters"
    if cat.startswith("P"):
        return "Punctuation"
    return "Symbols"


ORDER = ["Uppercase", "Lowercase", "Numerals & fractions", "Punctuation",
         "Currency", "Symbols", "Arrows", "Accented letters", "Combining marks"]


def charsets(font):
    buckets = {g: [] for g in ORDER}
    for cp in sorted(font.getBestCmap()):
        ch = chr(cp)
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "UNNAMED"
        buckets[group_of(cp, ch, unicodedata.category(ch))].append([cp, name])
    return [{"name": g, "chars": buckets[g]} for g in ORDER if buckets[g]]


def kb(path):
    return f"{round(os.path.getsize(path) / 1024)} KB"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FONTS, "GhostByte-Regular.otf")
    os.makedirs(FONTS, exist_ok=True)

    otf = os.path.join(FONTS, "GhostByte-Regular.otf")
    if os.path.abspath(src) != os.path.abspath(otf):
        shutil.copyfile(src, otf)

    for flavor, ext in (("woff2", "woff2"), ("woff", "woff")):
        f = TTFont(otf)
        f.flavor = flavor
        f.save(os.path.join(FONTS, f"GhostByte-Regular.{ext}"))
    build_ttf(otf, os.path.join(FONTS, "GhostByte-Regular.ttf"))

    shutil.copyfile(os.path.join(ROOT, "OFL.txt"), os.path.join(FONTS, "OFL.txt"))

    zip_name = f"GhostByte-v{VERSION}.zip"
    zip_path = os.path.join(ROOT, zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in ("otf", "ttf", "woff2", "woff"):
            p = os.path.join(FONTS, f"GhostByte-Regular.{ext}")
            z.write(p, os.path.basename(p))
        z.write(os.path.join(ROOT, "OFL.txt"), "OFL.txt")

    font = TTFont(otf)
    cmap = font.getBestCmap()
    os2 = font["OS/2"]
    html = open(TEMPLATE, encoding="utf-8").read()
    woff2 = os.path.join(FONTS, "GhostByte-Regular.woff2")

    tokens = {
        "__FONT_B64__": base64.b64encode(open(woff2, "rb").read()).decode(),
        "__CHARSET__": json.dumps(charsets(font)),
        "__N_CHARS__": str(len(cmap)),
        "__N_GLYPHS__": str(len(font.getGlyphOrder())),
        "__UPM__": str(font["head"].unitsPerEm),
        "__CAP__": str(os2.sCapHeight),
        "__XH__": str(os2.sxHeight),
        "__VERSION__": VERSION,
        "__ZIP_NAME__": zip_name,
        "__SIZE_ZIP__": kb(zip_path),
        "__SIZE_OTF__": kb(otf),
        "__SIZE_TTF__": kb(os.path.join(FONTS, "GhostByte-Regular.ttf")),
        "__SIZE_WOFF2__": kb(woff2),
        "__SIZE_WOFF__": kb(os.path.join(FONTS, "GhostByte-Regular.woff")),
    }
    for k, v in tokens.items():
        html = html.replace(k, v)

    leftover = re.findall(r"__[A-Z0-9_]+__", html)
    if leftover:
        sys.exit(f"unreplaced tokens: {sorted(set(leftover))}")

    out = os.path.join(ROOT, "index.html")
    open(out, "w", encoding="utf-8").write(html)

    print(f"index.html      {kb(out)}")
    for ext in ("otf", "ttf", "woff2", "woff"):
        print(f"  .{ext:<12} {kb(os.path.join(FONTS, f'GhostByte-Regular.{ext}'))}")
    print(f"{zip_name}  {kb(zip_path)}")
    print(f"{len(cmap)} characters / {len(font.getGlyphOrder())} glyphs")

    if not [r for r in font["name"].names if r.nameID == 0]:
        print("\nWARNING: no copyright in the font's name table (nameID 0).")
    if not [r for r in font["name"].names if r.nameID in (13, 14)]:
        print("WARNING: no license in the font's name table (nameID 13/14).")


if __name__ == "__main__":
    main()
