# convert an image into NES CHR (graphics) data

import os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

PALETTE = ((0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255))

HELP_TEXT = f"""\
Convert an image into NES CHR (graphics) data.
Arguments: inputFile outputFile
Input file must be 192*128 pixels (24*16 tiles). Colours allowed:
{PALETTE}\
"""

def get_colour_conv_table(image):
    # get palette; convert from [R, G, B, ...] to [(R, G, B), ...]
    imgPal = image.getpalette()
    imgPal = [tuple(imgPal[i*3:(i+1)*3]) for i in range(len(imgPal) // 3)]

    # look for unsupported palette entries that are actually used
    if not set(imgPal[c[1]] for c in image.getcolors()).issubset(set(PALETTE)):
        sys.exit("Image contains unsupported colours.")

    # create a tuple that converts original colour indexes into PALETTE
    return tuple(PALETTE.index(c) for c in imgPal)

def get_tiles(image):
    # generate each tile as a tuple of 64 2-bit ints

    if image.width != 192 or image.height != 128:
        sys.exit(f"Image must be 192*128 pixels.")
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

def convert_tile_index(dstInd):
    # get source tile index from destination index;
    # source layout: 24*16
    # destination layout: 16*16 on the left, 8*16 on the right

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

def encode_tile(tile):
    # tile = 16 bytes, less significant bitplane first;
    # generate 1 byte per call
    for bp in range(2):
        for y in range(0, 64, 8):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (7 - x) for x in range(8)
            )

def main():
    # parse arguments
    if len(sys.argv) != 3:
        sys.exit(HELP_TEXT)
    (inputFile, outputFile) = sys.argv[1:3]
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")
    if os.path.exists(outputFile):
        sys.exit("Output file already exists.")

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
        srcInd = convert_tile_index(i)
        for byte in encode_tile(tiles[srcInd]):
            chrData.append(byte)

    # write data
    try:
        with open(outputFile, "wb") as handle:
            handle.seek(0)
            handle.write(chrData)
    except OSError:
        sys.exit("Error writing output file.")

main()
