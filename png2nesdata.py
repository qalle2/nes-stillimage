# convert an image into NES graphics data

import os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

IMAGE_SIZES = (  # (width, height) in tiles
    (24, 16),
    (16, 24),
)
INPUT_PALETTE = (  # (red, green, blue)
    (0x00, 0x00, 0x00),
    (0x55, 0x55, 0x55),
    (0xaa, 0xaa, 0xaa),
    (0xff, 0xff, 0xff),
)
PRG_OUT_FILE = "prg.bin"
CHR_OUT_FILE = "chr.bin"

# --- get_tiles ---------------------------------------------------------------

def get_colour_conv_table(image):
    # get palette in [R, G, B, ...] format
    imgPal = image.getpalette()
    # convert palette into [(R, G, B), ...] format
    imgPal = [tuple(imgPal[i*3:(i+1)*3]) for i in range(len(imgPal) // 3)]
    # get colours that are actually used, in [(R, G, B), ...] format
    coloursUsed = [imgPal[c[1]] for c in image.getcolors()]

    if not set(coloursUsed).issubset(set(INPUT_PALETTE)):
        sys.exit("Image contains unsupported colours.")

    # create a dict that converts original colour indexes into INPUT_PALETTE
    return dict(
        (imgPal.index(c), INPUT_PALETTE.index(c)) for c in coloursUsed
    )

def get_tiles(image):
    # generate each tile as a tuple of 64 2-bit ints

    if (
        (image.width, image.height)
        not in ((w * 8, h * 8) for (w, h) in IMAGE_SIZES)
    ):
        sys.exit(f"Unsupported image width or height.")
    if image.getcolors(4) is None:
        sys.exit("Too many colours in image.")

    # convert into indexed colour
    if image.mode != "P":
        image = image.convert(
            "P", dither=Image.Dither.NONE, palette=Image.Palette.ADAPTIVE
        )

    colourConvTable = get_colour_conv_table(image)

    # generate tiles
    for y in range(0, image.height, 8):
        for x in range(0, image.width, 8):
            yield tuple(
                colourConvTable[c]
                for c in image.crop((x, y, x + 8, y + 8)).getdata()
            )

# --- get_prg_data ------------------------------------------------------------

def get_prg_data(outputPalette, width, height):
    # generate each byte of PRG data;
    # outputPalette: a tuple of 4 ints;
    # width, height: image size in tiles

    # settings for name table, attribute table and sprites
    if (width, height) == (24, 16):
        (ntTopMargin, ntBottomMargin) = (8, 6)
        ntRects = (
            # width, height, startIndex, leftMargin, rightMargin
            (16, 16, 0, 4, 12),
        )
        (atTopMargin, atBottomMargin) = (2, 2)
        atRects = (
            # width, height, leftMargin, rightMargin
            (4, 4, 1, 3),
        )
        sprStartY = 4 * 16 - 8 - 1
        sprStartX = 20 * 8
    elif (width, height) == (16, 24):
        (ntTopMargin, ntBottomMargin) = (4, 2)
        ntRects = (
            # width, height, startIndex, leftMargin, rightMargin
            ( 8, 16,   0, 8, 16),
            (16,  8, 128, 8,  8),
        )
        (atTopMargin, atBottomMargin) = (1, 1)
        atRects = (
            # width, height, leftMargin, rightMargin
            (2, 4, 2, 4),
            (4, 2, 2, 2),
        )
        sprStartY = 2 * 16 - 8 - 1
        sprStartX = 16 * 8
    else:
        sys.exit("Error (should never happen).")

    # name table (32*30 bytes)
    yield from (0x00 for i in range(ntTopMargin * 32))
    for (w, h, si, lm, rm) in ntRects:
        for y in range(h):
            yield from (0x00           for x in range(lm))
            yield from (si + y * w + x for x in range(w))
            yield from (0x00           for x in range(rm))
    yield from (0x00 for i in range(ntBottomMargin * 32))

    # attribute table (8*8 bytes)
    yield from (0x55 for i in range(atTopMargin * 8))
    for (w, h, lm, rm) in atRects:
        for y in range(h):
            yield from (0x55 for i in range(lm))
            yield from (0x00 for i in range(w))
            yield from (0x55 for i in range(rm))
    yield from (0x55 for i in range(atBottomMargin * 8))

    # sprites (64*4 bytes)
    for y in range(8):
        for x in range(8):
            yield from (
                sprStartY + y * 16,   # Y position minus 1
                (y * 8 + x) * 2 + 1,  # tile index
                0b00000000,           # attributes
                sprStartX + x * 8,    # X position
            )

    # palette (8*4 bytes)
    yield from outputPalette                             # BG0
    yield from (outputPalette[0] for i in range(4))      # BG1
    for i in range(2):
        yield from (outputPalette[0], 0x00, 0x00, 0x00)  # BG2-BG3 (unused)
    yield from outputPalette                             # SPR0
    for i in range(3):
        yield from (outputPalette[0], 0x00, 0x00, 0x00)  # SPR1-SPR3 (unused)

    # horizontal & vertical scroll
    yield from (0, 8)

# --- get_chr_data ------------------------------------------------------------

def convert_tile_index(dstInd, srcWidth, srcHeight):
    # dstInd:    tile index in destination (pattern tables; 0-383)
    # srcWidth:  source image width in tiles
    # srcHeight: source image height in tiles
    # return:    tile index in source image (0 to srcWidth*srcHeight-1)
    # note: the NES requires the tiles of each sprite to be in consecutive
    #       indexes, the first of which must be even

    (dstY, dstX) = divmod(dstInd, 16)  # max. (15, 23)

    if (srcWidth, srcHeight) == (24, 16):
        if dstY < 16:
            # tiles (0,0)-(15,15) -> (0,0)-(15,15) (background)
            srcX = dstX
            srcY = dstY
        else:
            # tiles (16,0)-(23,15) -> (0,16)-(15,23) (sprites)
            srcX = dstX // 2 + 16
            srcY = (dstY - 16) * 2 + dstX % 2
    elif (srcWidth, srcHeight) == (16, 24):
        if dstY < 8:
            # tiles (0,0)-(7,15) -> (0,0)-(15,7) (background)
            srcX = dstX % 8
            srcY = dstY * 2 + dstX // 8 % 2
        elif dstY < 16:
            # tiles (0,16)-(15,23) -> (0,8)-(15,15) (background)
            srcX = dstX
            srcY = dstY + 8
        else:
            # tiles (8,0)-(15,15) -> (0,16)-(15,23) (sprites)
            srcX = dstX // 2 + 8
            srcY = (dstY - 16) * 2 + dstX % 2
    else:
        sys.exit("Error (should never happen).")

    return srcY * srcWidth + srcX

def encode_tile(tile):
    # tile = 16 bytes, less significant bitplane first;
    # generate 1 byte per call
    for bp in range(2):
        for y in range(0, 64, 8):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (7 - x) for x in range(8)
            )

def get_chr_data(tiles, width, height):
    # generate encoded tiles in correct order;
    # tiles: list of tuples of 64 2-bit ints;
    # width, height: image size in tiles
    for i in range(len(tiles)):
        srcInd = convert_tile_index(i, width, height)
        for byte in encode_tile(tiles[srcInd]):
            yield byte

# --- main --------------------------------------------------------------------

def main():
    # parse arguments
    if len(sys.argv) != 6:
        sys.exit("Converts an image into NES graphics data. See README.md.")
    inputFile = sys.argv[1]
    try:
        outputPalette = tuple(int(c, 16) for c in sys.argv[2:6])
    except ValueError:
        sys.exit("Output colours must be hexadecimal integers.")
    if min(outputPalette) < 0 or max(outputPalette) > 0x3f:
        sys.exit("Output colours must be 00-3f.")
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")

    # read tiles
    try:
        with open(inputFile, "rb") as handle:
            handle.seek(0)
            image = Image.open(handle)
            tiles = list(get_tiles(image))
    except OSError:
        sys.exit("Error reading input file.")

    # write PRG data
    try:
        with open(PRG_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_prg_data(
                outputPalette, image.width // 8, image.height // 8
            )))
    except OSError:
        sys.exit(f"Error writing {PRG_OUT_FILE}")

    # write CHR data
    try:
        with open(CHR_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_chr_data(
                tiles, image.width // 8, image.height // 8
            )))
    except OSError:
        sys.exit(f"Error writing {CHR_OUT_FILE}")

    print(f"Wrote {PRG_OUT_FILE} and {CHR_OUT_FILE}")

main()
