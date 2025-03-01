# convert an image into NES graphics data using another algorithm

import itertools, os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

# size of input image in attribute blocks (16*16 pixels each)
IMG_WIDTH  = 16
IMG_HEIGHT = 14

# palette of input image (red, green, blue)
INPUT_PALETTE = (
    (0x00, 0x00, 0x00),
    (0x55, 0x55, 0x55),
    (0xaa, 0xaa, 0xaa),
    (0xff, 0xff, 0xff),
)

# special tiles to write
BLANK_TILE  = 64 * (0,)  # filled with colour 0
UNUSED_TILE = 64 * (3,)  # filled with colour 3

# files to write (used by stillimage.asm)
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

    if image.width != IMG_WIDTH * 16 or image.height != IMG_HEIGHT * 16:
        sys.exit("Image size must be 256*224 pixels.")

    if image.getcolors(4) is None:
        sys.exit("The image must have 4 colours or less.")

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
                   atData[si     ]
                | (atData[si+   1] << 2)
                | (atData[si+16  ] << 4)
                | (atData[si+16+1] << 6)
            )

def get_prg_data(ntData, spriteData, outputPal):
    # generate each byte of PRG data;
    # ntData:     indexes to distinct background tiles;
    # spriteData: (X, Y, index_to_distinct_sprite_pairs) for each;
    # outputPal:  a tuple of 4 ints

    # name table (32*30 bytes)
    yield from (0x00 for i in range(2 * 32))  # top margin
    yield from ntData

    # attribute table (16*15 blocks, 8*8 bytes)
    yield from encode_at_data(16 * 15 * [0b00])

    # sprites (64 * 4 bytes)
    for (i, (x, y, t)) in enumerate(spriteData):
        yield from (
            y * 16 + 8 - 1,  # Y position minus 1
            t * 2 + 1,       # tile index
            0b00000000,      # attributes
            x * 8,           # X position
        )
    for i in range(64 - len(spriteData)):
        yield from (0xff, 0xff, 0xff, 0xff)  # unused (hide)

    # palette (8*4 bytes)
    yield from outputPal                             # BG0
    yield from (outputPal[0] for i in range(4))      # BG1
    for i in range(2):
        yield from (outputPal[0], 0x00, 0x00, 0x00)  # BG2-BG3 (unused)
    yield from outputPal                             # SPR0
    for i in range(3):
        yield from (outputPal[0], 0x00, 0x00, 0x00)  # SPR1-SPR3 (unused)

    # horizontal and vertical scroll
    yield from (0, 8)

# --- get_chr_data ------------------------------------------------------------

def encode_tile(tile):
    # tile = 16 bytes, less significant bitplane first;
    # generate 1 byte per call
    for bp in range(2):
        for y in range(0, 64, 8):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (7 - x) for x in range(8)
            )

def get_chr_data(tiles):
    # generate encoded tiles;
    # tiles: list of tuples of 64 2-bit ints
    for tile in tiles:
        for byte in encode_tile(tile):
            yield byte

# --- main --------------------------------------------------------------------

def parse_arguments():
    # parse command line arguments;
    # return (input_file, output_palette)

    if len(sys.argv) not in (2, 6):
        sys.exit("Converts an image into NES graphics data. See README.md.")

    inputFile = sys.argv[1]
    if len(sys.argv) == 6:
        try:
            outputPal = tuple(int(c, 16) for c in sys.argv[2:6])
        except ValueError:
            sys.exit("Output colours must be hexadecimal integers.")
    else:
        outputPal = (0x0f, 0x00, 0x10, 0x30)

    if min(outputPal) < 0 or max(outputPal) > 0x3f:
        sys.exit("Output colours must be 00-3f.")
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")

    return (inputFile, outputPal)

def print_status_msg(descr, value):
    print(f"{descr:26}: {value:3d}")

def assign_tiles_to_sprites(bgTiles):
    # assign as many 1*2-tile pairs as possible to sprites instead;
    # bgTiles: list of background tiles starting from top left, with
    #          duplicates; each tile is a tuple of 64 2-bit ints
    # return: (new_bgTiles, sprite_data)

    # (x, y, upperSpriteData, lowerSpriteData); unit of x and y: 1*2 tiles
    spriteData = []

    # run many rounds to find first the pairs that save the most background
    # tiles
    for round_ in range(6):
        for sprY in range(14):
            for sprX in range(32):
                # "up" = upper, "lo" = lower
                upTilePos =  sprY * 2      * 32 + sprX
                loTilePos = (sprY * 2 + 1) * 32 + sprX

                # tile counts: 1 is the best; increasing values are worse;
                # 0 (a blank tile) is the worst
                if bgTiles[upTilePos] == BLANK_TILE:
                    upTileCnt = 0
                else:
                    upTileCnt = bgTiles.count(bgTiles[upTilePos])
                if bgTiles[loTilePos] == BLANK_TILE:
                    loTileCnt = 0
                else:
                    loTileCnt = bgTiles.count(bgTiles[loTilePos])

                if (
                    (
                           round_ >= 0 and  upTileCnt == 1 and loTileCnt == 1
                        or round_ >= 1 and (upTileCnt == 1 or  loTileCnt == 1)
                        or round_ >= 2 and  upTileCnt == 2 and loTileCnt == 2
                        or round_ >= 3 and (upTileCnt == 2 or  loTileCnt == 2)
                        or round_ >= 4 and  upTileCnt == 3 and loTileCnt == 3
                        or round_ >= 5 and (upTileCnt == 3 or  loTileCnt == 3)
                    )
                    and len(spriteData) < 64
                    and sum(1 for s in spriteData if s[1] == sprY) < 8
                ):
                    # copy tiles from background to sprites
                    spriteData.append((
                        sprX, sprY,
                        bgTiles[upTilePos], bgTiles[loTilePos]
                    ))
                    bgTiles[upTilePos] = BLANK_TILE
                    bgTiles[loTilePos] = BLANK_TILE

    return (bgTiles, spriteData)

def main():
    (inputFile, outputPal) = parse_arguments()

    # read tiles
    try:
        with open(inputFile, "rb") as handle:
            handle.seek(0)
            image = Image.open(handle)
            bgTiles = list(get_tiles(image))
    except OSError:
        sys.exit("Error reading input file.")

    print_status_msg("Total tiles", len(bgTiles))
    print_status_msg(
        "Distinct colours", len(set(itertools.chain.from_iterable(bgTiles)))
    )

    distinctBgTiles = set(bgTiles) | set((BLANK_TILE,))
    print_status_msg("Distinct tiles", len(distinctBgTiles))
    print_status_msg(
        "Tiles occurring only once",
        sum(1 for t in distinctBgTiles if bgTiles.count(t) == 1)
    )

    # assign some background tiles to sprites instead
    (bgTiles, spriteData) = assign_tiles_to_sprites(bgTiles)
    spriteData.sort(key=lambda s: (s[1], s[0]))  # by Y and X
    distinctSpriteTilePairs = tuple(sorted(set(
        (t1, t2) for (x, y, t1, t2) in spriteData
    )))
    # convert into (x, y, index_to_distinct_sprites)
    spriteData = tuple(
        (x, y, distinctSpriteTilePairs.index((t1, t2)))
        for (x, y, t1, t2) in spriteData
    )
    print_status_msg("Sprites", len(spriteData))
    print_status_msg(
        "Distinct sprite tile pairs", len(distinctSpriteTilePairs)
    )

    # get distinct background tiles
    distinctBgTiles = tuple(sorted(set(bgTiles) | set((BLANK_TILE,))))
    print_status_msg("Distinct background tiles", len(distinctBgTiles))

    if len(distinctBgTiles) > 256:
        sys.exit("Error: more than 256 background tiles. Cannot continue.")

    # get name table data (indexes to distinct background tiles)
    ntData = tuple(distinctBgTiles.index(t) for t in bgTiles)

    # write PRG data
    try:
        with open(PRG_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_prg_data(ntData, spriteData, outputPal)))
    except OSError:
        sys.exit(f"Error writing {PRG_OUT_FILE}")
    print(f"Wrote {PRG_OUT_FILE}")

    # combine and pad tile data to 256+128 tiles
    tiles = (
        distinctBgTiles
        + (256 - len(distinctBgTiles)) * (UNUSED_TILE,)
        + tuple(itertools.chain.from_iterable(distinctSpriteTilePairs))
        + (64 - len(distinctSpriteTilePairs)) * 2 * (UNUSED_TILE,)
    )

    # write CHR data
    try:
        with open(CHR_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_chr_data(tiles)))
    except OSError:
        sys.exit(f"Error writing {CHR_OUT_FILE}")
    print(f"Wrote {CHR_OUT_FILE}")

main()
