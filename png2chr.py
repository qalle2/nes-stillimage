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

    # bits: dstInd = SCCCCCCCC (Side, Coordinates)

    if dstInd & 0x100 == 0:
        # S=0 (background);
        # bits: dstInd = 0YYYYXXXX
        #    ->   srcY =      YYYY
        #    ->   srcX =      XXXX
        srcY = (dstInd >> 4) & 0b1111
        srcX =  dstInd       & 0b1111
    else:
        # S=1 (sprites);
        # bits: dstInd = 10YYyXXXx
        #    ->   srcY =      yYYx
        #    ->   srcX =     10XXX
        srcY = (
              (dstInd >> 1) & 0b1000
            | (dstInd >> 4) &  0b110
            |  dstInd       &    0b1
        )
        srcX = (
               0b10000
            | (dstInd >> 1) & 0b111
        )

    return srcY * 24 + srcX

def encode_tile(tile):
    # generate 1 byte per call
    for bitplane in range(2):
        for y in range(0, 64, 8):
            yield sum(
                ((tile[y+x] >> bitplane) & 1) << (7 - x)
                for x in range(8)
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
