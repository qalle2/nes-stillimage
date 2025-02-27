# convert an image into NES graphics data

import os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

IMAGE_SIZES = ((24, 16), (16, 24))  # (width, height) in tiles
INPUT_PALETTE = ((0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255))
PRG_FILE = "prg.bin"  # to write
CHR_FILE = "chr.bin"  # to write

def get_colour_conv_table(image):
    # get palette; convert from [R, G, B, ...] to [(R, G, B), ...]
    imgPal = image.getpalette()
    imgPal = [tuple(imgPal[i*3:(i+1)*3]) for i in range(len(imgPal) // 3)]

    # look for unsupported palette entries that are actually used
    if not set(imgPal[c[1]] for c in image.getcolors()).issubset(
        set(INPUT_PALETTE)
    ):
        sys.exit("Image contains unsupported colours.")

    # create a tuple that converts original colour indexes into INPUT_PALETTE
    return tuple(INPUT_PALETTE.index(c) for c in imgPal)

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

def convert_tile_index_24x16(dstInd):
    # get source tile index from destination index;
    # source layout: 24*16;
    # destination layout: BG 16*16 on the left, SPR 8*16 on the right

    # bits: dstInd = SYYYYXXXX (Side, Y position, X position)
    (side, dstY) = divmod(dstInd, 0x100)
    (dstY, dstX) = divmod(dstY,   0x10)

    if side == 0:
        # background
        srcY = dstY
        srcX = dstX
    else:
        # sprites (dstY <= 7);
        # the NES requires the tiles of a sprite to be in consecutive indexes
        srcY = (dstY << 1) | dstX & 0b1
        srcX = 0b10000 | (dstX >> 1)

    return srcY * 24 + srcX

def convert_tile_index_16x24(dstInd):
    # get source tile index from destination index;
    # source layout: 16*24;
    # destination layout:
    #   - BG   8*16 on top left (tiles   0-127)
    #   - BG  16* 8 on bottom   (tiles 128-255)
    #   - SPR  8*16 on top right

    dstY = dstInd >> 4      # 0-23
    dstX = dstInd & 0b1111  # 0- 7

    if dstY < 8:
        # top left (BG)
        srcY = (dstY << 1) & 0b1110 | (dstX >> 3) & 0b1
        srcX = dstX & 0b111
    elif dstY < 16:
        # bottom (BG)
        srcY = 0b10000 | (dstY & 0b111)
        srcX = dstX & 0b1111
    else:
        # top right (sprites)
        # -> 00 08 01 09 ...
        srcY = (dstX & 0b1) | (dstY << 1) & 0b1110
        srcX = 8 | (dstX >> 1)

    return srcY * 16 + srcX

def encode_tile(tile):
    # tile = 16 bytes, less significant bitplane first;
    # generate 1 byte per call
    for bp in range(2):
        for y in range(0, 64, 8):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (7 - x) for x in range(8)
            )

def get_prg_data(width, height, outputColours):
    # generate each byte of PRG data;
    # width, height: image size in tiles
    # outputColours: 4 bytes

    if (width, height) == (24 * 8, 16 * 8):
        # NT - top margin
        yield from (0x00 for i in range(8*32))
        # NT - the image itself
        for y in range(16):
            yield from (0x00       for x in range( 4))
            yield from (y * 16 + x for x in range(16))
            yield from (0x00       for x in range(12))
        # NT - bottom margin
        yield from (0x00 for i in range(6*32))

        # AT - top margin
        for y in range(2):
            yield from (0x55 for i in range(8))
        # AT - the image itself
        for y in range(4):
            yield from (0x55,0x00,0x00,0x00,0x00,0x55,0x55,0x55)
        # AT - bottom margin
        for y in range(2):
            yield from (0x55 for i in range(8))

        # sprites
        for y in range(8):
            for x in range(8):
                yield (4 + y) * 16 - 8 - 1  # Y position minus 1
                yield (y * 8 + x) * 2 + 1   # tile index
                yield 0b00000000            # attributes
                yield (20 + x) * 8          # X position

        # palette
        for i in range(2):
            # BG0, SPR0
            yield from outputColours
            # BG1-BG3, SPR1-SPR3 (only BG1 used)
            yield from (outputColours[0] for i in range(3*4))

        # horizontal & vertical scroll
        yield from (0, 8)

    else:
        # NT
        yield from (0x00 for i in range(4*32))
        for y in range(16):
            yield from (0x00      for x in range( 8))
            yield from (y * 8 + x for x in range( 8))
            yield from (0x00      for x in range(16))
        for y in range(8):
            yield from (0x00             for x in range( 8))
            yield from (128 + y * 16 + x for x in range(16))
            yield from (0x00             for x in range( 8))
        yield from (0x00 for i in range(2*32))

        # AT - top margin
        for y in range(1):
            yield from (0x55 for i in range(8))
        # AT - the image itself
        for y in range(4):
            yield from (0x55,0x55,0x00,0x00,0x55,0x55,0x55,0x55)
        for y in range(2):
            yield from (0x55,0x55,0x00,0x00,0x00,0x00,0x55,0x55)
        # AT - bottom margin
        for y in range(1):
            yield from (0x55 for i in range(8))

        # sprites
        for y in range(8):
            for x in range(8):
                yield (2 + y) * 16 - 8 - 1  # Y position minus 1
                yield (y * 8 + x) * 2 + 1   # tile index
                yield 0b00000000            # attributes
                yield (16 + x) * 8          # X position

        # palette
        for i in range(2):
            # BG0, SPR0
            yield from outputColours
            # BG1-BG3, SPR1-SPR3 (only BG1 used)
            yield from (outputColours[0] for i in range(3*4))

        # horizontal & vertical scroll
        yield from (0, 8)

def main():
    # parse arguments
    if len(sys.argv) != 6:
        sys.exit("Converts an image into NES graphics data. See README.md.")
    inputFile = sys.argv[1]
    try:
        outputColours = tuple(int(c, 16) for c in sys.argv[2:6])
    except ValueError:
        sys.exit("Output colours must be hexadecimal integers.")
    if min(outputColours) < 0 or max(outputColours) > 0x3f:
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

    # encode tiles
    chrData = bytearray()
    for i in range(len(tiles)):
        if (image.width, image.height) == (24 * 8, 16 * 8):
            srcInd = convert_tile_index_24x16(i)
        else:
            srcInd = convert_tile_index_16x24(i)
        for byte in encode_tile(tiles[srcInd]):
            chrData.append(byte)

    # write PRG data
    try:
        with open(PRG_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(
                get_prg_data(image.width, image.height, outputColours)
            ))
    except OSError:
        sys.exit(f"Error writing {PRG_FILE}")

    # write CHR data
    try:
        with open(CHR_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(chrData)
    except OSError:
        sys.exit(f"Error writing {CHR_FILE}")

    print(f"Wrote {PRG_FILE} and {CHR_FILE}")

main()
