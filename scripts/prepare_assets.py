#!/usr/bin/env python3
"""
SomaiyaSat Ground Control -- one-time asset preparation for the landing page.

Downloads the public-domain NASA Earth imagery the 3D scenes need, resizes it to
power-of-two textures, and derives a land/water mask that the point-cloud Earth
and the halftone world map are both generated from at runtime.

Everything it writes is committed to landing/public/assets, so the UI works with
the network disconnected. Re-running is cheap: files already present are skipped
unless --force is given.

    python scripts/prepare_assets.py [--force]

Optional: if public/assets/source/KJS-SRS-01.pdf is present, figures are extracted
from it as well (needs PyMuPDF). The build does not depend on that PDF.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
TEX = ROOT / "landing" / "public" / "assets" / "textures"
IMG = ROOT / "landing" / "public" / "assets" / "img"
SRC = ROOT / "landing" / "public" / "assets" / "source"

# NASA Visible Earth. Public domain (NASA media usage guidelines).
SOURCES = {
    "earth_day.jpg": (
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/"
        "world.topo.bathy.200412.3x5400x2700.jpg",
        "NASA Visible Earth - Blue Marble Next Generation (Dec 2004)",
    ),
    "earth_night.jpg": (
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/"
        "dnb_land_ocean_ice.2012.3600x1800.jpg",
        "NASA Earth Observatory - Black Marble / VIIRS night lights (2012)",
    ),
}

# Elevation, used as a bump map so the dashboard globe shows relief.
# The source is a 21600x10800 PNG (~18 MB); it is downloaded once and
# immediately downsampled to a small greyscale map, which is all a bump map
# needs. Optional: everything still works if this fetch fails.
BUMP_SOURCE = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73934/"
    "gebco_08_rev_elev_21600x10800.png",
    "NASA Visible Earth - GEBCO / SRTM elevation",
)

DAY_SIZE = (4096, 2048)
NIGHT_SIZE = (4096, 2048)
MASK_SIZE = (1024, 512)
BUMP_SIZE = (2048, 1024)

# Cloud cover, drawn as a translucent shell above the surface. This is the
# single biggest depth cue on the dashboard globe.
CLOUD_SOURCE = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57747/"
    "cloud_combined_2048.jpg",
    "NASA Visible Earth - Blue Marble cloud composite",
)
CLOUD_SIZE = (2048, 1024)
SPEC_SIZE = (1024, 512)


def fetch(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "somaiyasat-ground-control/1.0"})
    with urlopen(req, timeout=120) as r, dest.open("wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required:  pip install pillow", file=sys.stderr)
        raise SystemExit(1)

    for d in (TEX, IMG, SRC):
        d.mkdir(parents=True, exist_ok=True)

    raw_day = TEX / "_raw_day.jpg"
    raw_night = TEX / "_raw_night.jpg"
    raws = {"earth_day.jpg": raw_day, "earth_night.jpg": raw_night}

    # ---- download ---------------------------------------------------------
    for name, (url, credit) in SOURCES.items():
        out = TEX / name
        if out.exists() and not args.force:
            print(f"  skip     {name} (exists)")
            continue
        raw = raws[name]
        print(f"  download {name} <- {credit}")
        try:
            fetch(url, raw)
        except Exception as exc:
            print(f"  FAILED   {name}: {exc}", file=sys.stderr)
            if not out.exists():
                print("           the landing page will fall back to flat colours.")
            continue

        size = DAY_SIZE if name == "earth_day.jpg" else NIGHT_SIZE
        with Image.open(raw) as im:
            im = im.convert("RGB").resize(size, Image.LANCZOS)
            im.save(out, "JPEG", quality=86, optimize=True)
        raw.unlink(missing_ok=True)
        print(f"           -> {out.relative_to(ROOT)}  {size[0]}x{size[1]}")

    # ---- elevation bump map ------------------------------------------------
    bump_out = TEX / "earth_topology.jpg"
    if bump_out.exists() and not args.force:
        print("  skip     earth_topology.jpg (exists)")
    else:
        url, credit = BUMP_SOURCE
        raw_bump = TEX / "_raw_bump.png"
        print(f"  download earth_topology.jpg <- {credit}")
        print("           (~18 MB, downsampled straight after)")
        try:
            fetch(url, raw_bump)
            # 21600x10800 is 233 Mpx, over Pillow's 178 Mpx decompression-bomb
            # guard. The guard is there for untrusted input; this is a known
            # NASA asset we just downloaded from a known URL, so lift it for
            # this one decode and put it straight back.
            prev_limit = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = 300_000_000
            try:
                with Image.open(raw_bump) as im:
                    im = im.convert("L").resize(BUMP_SIZE, Image.LANCZOS)
                    im.save(bump_out, "JPEG", quality=88, optimize=True)
            finally:
                Image.MAX_IMAGE_PIXELS = prev_limit
            print(f"           -> {bump_out.relative_to(ROOT)}  "
                  f"{BUMP_SIZE[0]}x{BUMP_SIZE[1]} greyscale")
        except Exception as exc:
            print(f"  FAILED   earth_topology.jpg: {exc}", file=sys.stderr)
            print("           the globe just renders without surface relief.")
        finally:
            raw_bump.unlink(missing_ok=True)

    # ---- land mask --------------------------------------------------------
    # Derived from the day texture: Blue Marble ocean is strongly blue-dominant,
    # while land (soil, vegetation) and ice are not. White = land, black = water.
    mask_out = TEX / "land_mask.png"
    day = TEX / "earth_day.jpg"
    if day.exists() and (args.force or not mask_out.exists()):
        print("  derive   land_mask.png from earth_day.jpg")
        with Image.open(day) as im:
            small = im.convert("RGB").resize(MASK_SIZE, Image.BILINEAR)
            px = small.load()
            mask = Image.new("L", MASK_SIZE, 0)
            mp = mask.load()
            w, h = MASK_SIZE
            for y in range(h):
                for x in range(w):
                    r, g, b = px[x, y]
                    # Ocean: blue channel clearly leads and the pixel is dark-ish.
                    is_water = (b > r + 12) and (b > g + 6) and (r < 120)
                    mp[x, y] = 0 if is_water else 255
            mask.save(mask_out, "PNG", optimize=True)
        land = sum(1 for y in range(MASK_SIZE[1]) for x in range(MASK_SIZE[0])
                   if mask.load()[x, y] > 127)
        pct = 100.0 * land / (MASK_SIZE[0] * MASK_SIZE[1])
        print(f"           -> {mask_out.relative_to(ROOT)}  land={pct:.1f}% of pixels")
    elif mask_out.exists():
        print("  skip     land_mask.png (exists)")

    # ---- clouds -----------------------------------------------------------
    cloud_out = TEX / "earth_clouds.jpg"
    if cloud_out.exists() and not args.force:
        print("  skip     earth_clouds.jpg (exists)")
    else:
        url, credit = CLOUD_SOURCE
        raw_cloud = TEX / "_raw_cloud.jpg"
        print(f"  download earth_clouds.jpg <- {credit}")
        try:
            fetch(url, raw_cloud)
            with Image.open(raw_cloud) as im:
                im = im.convert("L").resize(CLOUD_SIZE, Image.LANCZOS)
                im.save(cloud_out, "JPEG", quality=86, optimize=True)
            print(f"           -> {cloud_out.relative_to(ROOT)}  "
                  f"{CLOUD_SIZE[0]}x{CLOUD_SIZE[1]} greyscale")
        except Exception as exc:
            print(f"  FAILED   earth_clouds.jpg: {exc}", file=sys.stderr)
            print("           the globe renders without a cloud layer.")
        finally:
            raw_cloud.unlink(missing_ok=True)

    # ---- ocean specular map -----------------------------------------------
    # Just the land mask inverted: water reflects the sun, land does not.
    # That glint is what stops the oceans reading as flat paint.
    spec_out = TEX / "earth_specular.jpg"
    if mask_out.exists() and (args.force or not spec_out.exists()):
        print("  derive   earth_specular.jpg from land_mask.png")
        try:
            from PIL import ImageFilter, ImageOps
            with Image.open(mask_out) as m:
                spec = ImageOps.invert(m.convert("L")).resize(SPEC_SIZE, Image.LANCZOS)
                # soften the coastline so the glint does not have a hard edge
                spec = spec.filter(ImageFilter.GaussianBlur(1.2))
                spec.save(spec_out, "JPEG", quality=88, optimize=True)
            print(f"           -> {spec_out.relative_to(ROOT)}  "
                  f"{SPEC_SIZE[0]}x{SPEC_SIZE[1]} (white = water)")
        except Exception as exc:
            print(f"  FAILED   earth_specular.jpg: {exc}", file=sys.stderr)
    elif spec_out.exists():
        print("  skip     earth_specular.jpg (exists)")

    # ---- optional: figures out of the use-case PDF ------------------------
    pdf = SRC / "KJS-SRS-01.pdf"
    if pdf.exists():
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("  note     KJS-SRS-01.pdf found but PyMuPDF is not installed;")
            print("           pip install pymupdf  then re-run to extract figures.")
        else:
            print("  extract  figures from KJS-SRS-01.pdf")
            doc = fitz.open(pdf)
            n = 0
            for page in doc:
                for i, info in enumerate(page.get_images(full=True)):
                    xref = info[0]
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < 200 or pix.height < 200:
                        continue
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    n += 1
                    out = IMG / f"fig_{n:02d}_p{page.number + 1}_{i}.png"
                    pix.save(out)
                    print(f"           -> {out.name}  {pix.width}x{pix.height}")
            doc.close()
            if n == 0:
                print("           no embedded raster figures found.")
    else:
        print("  note     no KJS-SRS-01.pdf in landing/public/assets/source/")
        print("           the Build section uses original artwork instead.")

    print("\nAssets ready in landing/public/assets/")


if __name__ == "__main__":
    main()
