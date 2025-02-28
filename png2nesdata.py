# convert an image into NES graphics data

import os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

IMAGE_SIZES = (  # (width, height) in attribute blocks (16*16 pixels each)
    (13,  7),
    (12,  8),
    (10,  9),
    ( 9, 10),
    ( 8, 12),
    ( 7, 13),
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
        not in ((w * 16, h * 16) for (w, h) in IMAGE_SIZES)
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

def encode_at_data(atData):
    # encode attribute table data
    # atData:   a list of 240 (16*15) 2-bit ints
    # generate: 64 8-bit ints

    # pad to 16*16 attribute blocks (last one unused by the NES)
    atData.extend(16 * [0])

    for y in range(8):
        for x in range(8):
            si = (y * 16 + x) * 2  # source index
            yield (
                   atData[si]
                | (atData[si+1]    << 2)
                | (atData[si+16]   << 4)
                | (atData[si+16+1] << 6)
            )

def get_prg_data(outputPalette, width, height):
    # generate each byte of PRG data;
    # outputPalette: a tuple of 4 ints;
    # width, height: image size in attribute blocks (16 pixels)

    # settings for attribute table
    atRects = (
        # (width, height) in AT blocks
        (width - 4, min(height,     8)),  # at top left of image
        (width,     max(height - 8, 0)),  # at bottom   of image
    )
    atTopMargin    = (15 - height + 1) // 2  # = bottom or bottom + 1
    atBottomMargin = (15 - height    ) // 2
    atLeftMargin   = (16 - width  + 1) // 2  # = right  or right  + 1

    # name table (32*30 bytes; just multiply all AT sizes by 2)
    yield from (0x00 for i in range(atTopMargin * 2 * 32))
    startInd = 0
    for (w, h) in atRects:
        w *= 2
        h *= 2
        for y in range(h):
            yield from (0x00 for x in range(atLeftMargin * 2))
            yield from (startInd + y * w + x for x in range(w))
            yield from (0x00 for x in range(32 - atLeftMargin * 2 - w))
        startInd += w * h
    yield from (0x00 for i in range(atBottomMargin * 2 * 32))

    # attribute table (16*15 blocks, 8*8 bytes)
    atBlocks = []
    atBlocks.extend(1 for i in range(atTopMargin * 16))
    for (w, h) in atRects:
        for y in range(h):
            atBlocks.extend(1 for i in range(atLeftMargin))
            atBlocks.extend(0 for i in range(w))
            atBlocks.extend(1 for i in range(16 - atLeftMargin - w))
    atBlocks.extend(1 for i in range(atBottomMargin * 16))
    yield from encode_at_data(atBlocks)

    # sprites (64*4 bytes)
    sprStartX = ( 8 + width ) * 8
    sprStartY = (15 - height) * 8 - 1
    for y in range(8):
        for x in range(8):
            if y >= height:
                # unused (hide)
                yield from (0xff, 0xff, 0xff, 0xff)
            else:
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

    yield from (
             width  % 2  * 8,  # horizontal scroll
        (1 - height % 2) * 8,  # vertical   scroll
    )

# --- get_chr_data ------------------------------------------------------------

def convert_tile_index(dstInd, srcWidth, srcHeight):
    # dstInd:    tile index in destination (pattern tables; 0-383)
    # srcWidth:  source image width  in attribute blocks (16 pixels each)
    # srcHeight: source image height in attribute blocks (16 pixels each)
    # return:    tile index in source image (0 to srcWidth*srcHeight-1),
    #            or -1 for a blank tile
    # note: the NES requires the tiles of each sprite to be in consecutive
    #       indexes, the first of which must be even

    (dstY, dstX) = divmod(dstInd, 16)  # max. (23, 15)

    if (srcWidth, srcHeight) == (13, 7):  # 26*14 tiles
        if dstY < 15 or dstY == 15 and dstX < 12:
            # tiles (0,0)-(17,13) -> (0,0)-(15,15) (background)
            (srcY, srcX) = divmod(dstInd, 18)
        elif dstY < 16:
            # unused (background)
            (srcY, srcX) = (0, -1)
        elif dstY < 23:
            # tiles (18,0)-(25,13) -> (0,16)-(15,22) (sprites)
            srcX = 18 + dstX // 2
            srcY = (dstY - 16) * 2 + dstX % 2
        else:
            # unused (sprites)
            (srcY, srcX) = (0, -1)
    elif (srcWidth, srcHeight) == (12, 8):  # 24*16 tiles
        if dstY < 16:
            # tiles (0,0)-(15,15) -> (0,0)-(15,15) (background)
            (srcY, srcX) = (dstY, dstX)
        else:
            # tiles (16,0)-(23,15) -> (0,16)-(15,23) (sprites)
            srcX = 16 + dstX // 2
            srcY = (dstY - 16) * 2 + dstX % 2
    elif (srcWidth, srcHeight) == (10, 9):  # 20*18 tiles
        if dstY < 12:
            # tiles (0,0)-(11,15) -> (0,0)-(15,11) (background)
            (srcY, srcX) = divmod(dstInd, 12)
        elif dstY < 14 or dstY == 14 and dstX < 8:
            # tiles (0,16)-(19,17) -> (0,12)-(15,14) (background)
            (srcY, srcX) = divmod(dstInd - 16 * 12, 20)
            srcY += 16
        elif dstY < 16:
            # unused (background)
            (srcY, srcX) = (0, -1)
        else:
            # tiles (12,0)-(19,15) -> (0,16)-(15,23) (sprites)
            srcX = dstX // 2 + 12
            srcY = (dstY - 16) * 2 + dstX % 2
    elif (srcWidth, srcHeight) == (9, 10):  # 18*20 tiles
        if dstY < 10:
            # tiles (0,0)-(9,15) -> (0,0)-(15,9) (background)
            (srcY, srcX) = divmod(dstInd, 10)
        elif dstY < 14 or dstY == 14 and dstX < 8:
            # tiles (0,16)-(17,19) -> (0,10)-(15,14) (background)
            (srcY, srcX) = divmod(dstInd - 16 * 10, 18)
            srcY += 16
        elif dstY < 16:
            # unused (background)
            (srcY, srcX) = (0, -1)
        else:
            # tiles (10,0)-(17,15) -> (0,16)-(15,23) (sprites)
            srcX = 10 + dstX // 2
            srcY = (dstY - 16) * 2 + dstX % 2
    elif (srcWidth, srcHeight) == (8, 12):  # 16*24 tiles
        if dstY < 8:
            # tiles (0,0)-(7,15) -> (0,0)-(15,7) (background)
            (srcY, srcX) = divmod(dstInd, 8)
        elif dstY < 16:
            # tiles (0,16)-(15,23) -> (0,8)-(15,15) (background)
            (srcY, srcX) = (dstY + 8, dstX)
        else:
            # tiles (8,0)-(15,15) -> (0,16)-(15,23) (sprites)
            srcX = 8 + dstX // 2
            srcY = (dstY - 16) * 2 + dstX % 2
    elif (srcWidth, srcHeight) == (7, 13):  # 14*26 tiles
        if dstY < 6:
            # tiles (0,0)-(5,15) -> (0,0)-(15,5) (background)
            (srcY, srcX) = divmod(dstInd, 6)
        elif dstY < 14 or dstY == 14 and dstX < 12:
            # tiles (0,16)-(13,25) -> (0,6)-(15,14) (background)
            (srcY, srcX) = divmod(dstInd - 16 * 6, 14)
            srcY += 16
        elif dstY < 16:
            # unused (background)
            (srcY, srcX) = (0, -1)
        else:
            # tiles (6,0)-(13,15) -> (0,16)-(15,23) (sprites)
            srcX = 6 + dstX // 2
            srcY = (dstY - 16) * 2 + dstX % 2
    else:
        sys.exit("Error (should never happen).")

    return srcY * (srcWidth * 2) + srcX

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
    # width, height: image size in attribute blocks (16 pixels each)
    for i in range(16 * 24):
        srcInd = convert_tile_index(i, width, height)
        tileData = 64 * (3,) if srcInd == -1 else tiles[srcInd]  # -1 = unused
        for byte in encode_tile(tileData):
            yield byte

# --- main --------------------------------------------------------------------

def parse_arguments():
    # parse command line arguments; return (inputFile, outputPalette)

    if len(sys.argv) not in (2, 6):
        sys.exit("Converts an image into NES graphics data. See README.md.")

    inputFile = sys.argv[1]
    if len(sys.argv) == 6:
        try:
            outputPalette = tuple(int(c, 16) for c in sys.argv[2:6])
        except ValueError:
            sys.exit("Output colours must be hexadecimal integers.")
    else:
        outputPalette = (0x0f, 0x00, 0x10, 0x30)

    if min(outputPalette) < 0 or max(outputPalette) > 0x3f:
        sys.exit("Output colours must be 00-3f.")
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")

    return (inputFile, outputPalette)

def main():
    (inputFile, outputPalette) = parse_arguments()

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
                outputPalette, image.width // 16, image.height // 16
            )))
    except OSError:
        sys.exit(f"Error writing {PRG_OUT_FILE}")

    # write CHR data
    try:
        with open(CHR_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_chr_data(
                tiles, image.width // 16, image.height // 16
            )))
    except OSError:
        sys.exit(f"Error writing {CHR_OUT_FILE}")

    print(f"Wrote {PRG_OUT_FILE} and {CHR_OUT_FILE}")

main()
