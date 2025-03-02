# convert an image into NES graphics data

import collections, itertools, os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

# --- "constants" -------------------------------------------------------------

# NES hardware-specific values; don't change these
TILE_WIDTH               =   8  # tile       width  in pixels
TILE_HEIGHT              =   8  # tile       height in pixels
NT_WIDTH                 =  32  # name table width  in tiles
NT_HEIGHT                =  30  # name table height in tiles
MAX_BG_TILES             = 256  # maximum number of distinct background tiles
MAX_SPRITES              =  64  # maximum number of sprites
MAX_SPRITES_PER_SCANLINE =   8  # maximum number of sprites per scanline

# the rest of the "constants" can be changed

# palette of input image (red, green, blue)
INPUT_PALETTE = (
    (0x00, 0x00, 0x00),
    (0x55, 0x55, 0x55),
    (0xaa, 0xaa, 0xaa),
    (0xff, 0xff, 0xff),
)
# default output palette (four NES colour indexes)
DEFAULT_OUT_PALETTE = (0x0f, 0x00, 0x10, 0x30)

# files to write (used by stillimage.asm)
PRG_OUT_FILE = "prg.bin"
CHR_OUT_FILE = "chr.bin"

# only decrease these if can't let this program have all the sprites;
# minimum: 0, maximum: MAX_SPRITES_PER_SCANLINE and MAX_SPRITES, respectively
MAX_SPRITES_PER_SCANLINE_TO_USE = MAX_SPRITES_PER_SCANLINE
MAX_SPRITES_TO_USE              = MAX_SPRITES

BLANK_TILE_INDEX = 0
BLANK_TILE  = TILE_WIDTH * TILE_HEIGHT * (0,)  # filled with colour 0
UNUSED_TILE = TILE_WIDTH * TILE_HEIGHT * (3,)  # filled with colour 3

# --- functions except main ---------------------------------------------------

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
        outputPal = DEFAULT_OUT_PALETTE

    if min(outputPal) < 0 or max(outputPal) > 0x3f:
        sys.exit("Output colours must be 00-3f.")
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")

    return (inputFile, outputPal)

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
    # generate each tile as a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints

    if not 8 <= image.width <= 256 or image.width % 8 > 0:
        sys.exit("Image width must be 8-256 and a multiple of 8.")
    if not 8 <= image.height <= 224 or image.height % 8 > 0:
        sys.exit("Image height must be 8-224 and a multiple of 8.")
    if image.getcolors(4) is None:
        sys.exit("The image must have 4 colours or less.")

    # convert into indexed colour
    if image.mode != "P":
        image = image.convert(
            "P", dither=Image.Dither.NONE, palette=Image.Palette.ADAPTIVE
        )

    colourConvTable = get_colour_conv_table(image)

    # generate tiles
    for y in range(0, image.height, TILE_HEIGHT):
        for x in range(0, image.width, TILE_WIDTH):
            yield tuple(
                colourConvTable[c]
                for c in image.crop(
                    (x, y, x + TILE_WIDTH, y + TILE_HEIGHT)
                ).getdata()
            )

def get_tile_distance(tile1, tile2):
    # tile1, tile2: tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    return sum(abs(a - b) for (a, b) in zip(tile1, tile2))

def assign_tiles_to_sprites(imgTiles, imgWidth, imgHeight):
    # assign as many 1*2-tile pairs as possible to sprites instead
    # imgTiles:  list of image tile indexes starting from top left, with
    #            duplicates
    # imgWidth:  image width  in tiles
    # imgHeight: image height in tiles
    # return:    (background_tile_indexes, sprite_data);
    #            sprite_data is: (x, y, upper_sprite, lower_sprite);
    #            x, y are in tiles;
    #            upper_sprite, lower_sprite are image tile indexes

    bgTiles    = imgTiles.copy()
    spriteData = []

    if min(MAX_SPRITES_PER_SCANLINE_TO_USE, MAX_SPRITES_TO_USE) == 0:
        return (bgTiles, spriteData)

    # replace 1*2-tile pairs where both tiles are non-blank and unique within
    # the image; this way each sprite saves 2 background tiles;
    # if the height is odd, don't bother looking at the last row
    for sprY in range(0, imgHeight - 1, 2):
        spritesPerRow = 0
        for sprX in range(imgWidth):
            upperTilePos =  sprY      * imgWidth + sprX
            lowerTilePos = (sprY + 1) * imgWidth + sprX
            if (
                    bgTiles[upperTilePos] != BLANK_TILE_INDEX
                and bgTiles[lowerTilePos] != BLANK_TILE_INDEX
                and bgTiles.count(bgTiles[upperTilePos]) == 1
                and bgTiles.count(bgTiles[lowerTilePos]) == 1
            ):
                # move tiles from background to sprites
                spriteData.append((
                    sprX, sprY, bgTiles[upperTilePos], bgTiles[lowerTilePos]
                ))
                bgTiles[upperTilePos] = BLANK_TILE_INDEX
                bgTiles[lowerTilePos] = BLANK_TILE_INDEX
                spritesPerRow += 1
                if (
                      spritesPerRow    == MAX_SPRITES_PER_SCANLINE_TO_USE
                    or len(spriteData) == MAX_SPRITES_TO_USE
                ):
                    break
        if len(spriteData) == MAX_SPRITES_TO_USE:
            break

    return (bgTiles, spriteData)

def get_tile_to_replace(
    origTileCnt, tileDistances, tileCnts, distinctTilesLeft
):
    # which distinct tile to eliminate with the smallest error possible?
    #   origTileCnt:       original number of distinct tiles
    #   tileDistances:     a look-up table for distances between tiles;
    #                      index: (tile_index1 * origTileCnt + tile_index2)
    #   tileCnts:          {tile_index: count_in_image, ...}
    #   distinctTilesLeft: set of indexes to original distinct tiles
    #   return:            tile to replace: (from_index, to_index)

    minTotalDiff = -1
    for fromInd in distinctTilesLeft:
        if fromInd != BLANK_TILE_INDEX:
            # find the closest match for this tile
            minDiff = -1
            for toInd in distinctTilesLeft:
                if toInd != fromInd:
                    dist = tileDistances[fromInd*origTileCnt+toInd]
                    if minDiff == -1 or dist < minDiff:
                        minDiff   = dist
                        bestToInd = toInd
            # remember this tile and its replacement if they result in the
            # smallest total error so far
            totalDiff = minDiff * tileCnts[fromInd]
            if minTotalDiff == -1 or totalDiff < minTotalDiff:
                minTotalDiff     = totalDiff
                bestFromInd      = fromInd
                overallBestToInd = bestToInd

    return (bestFromInd, overallBestToInd)

def encode_at_data(atData):
    # encode attribute table data
    # atData:   a list of 240 (16*15) 2-bit ints
    # generate: 64 8-bit ints

    # pad to 16*16 attribute blocks (last row unused by the NES)
    atData.extend(0b00 for i in range(16 * 16 - len(atData)))

    for y in range(8):
        for x in range(8):
            si = (y * 16 + x) * 2  # source index
            yield (
                   atData[si     ]
                | (atData[si+   1] << 2)
                | (atData[si+16  ] << 4)
                | (atData[si+16+1] << 6)
            )

def get_prg_data(ntData, spriteData, outputPal, imgWidth, imgHeight):
    # generate each byte of PRG data;
    # ntData:     indexes to distinct background tiles
    # spriteData: (X, Y, index_to_distinct_sprite_pairs) for each
    # outputPal:  a tuple of 4 ints
    # imgWidth:   image width  in tiles
    # imgHeight:  image height in tiles

    # name table; (NT_WIDTH * NT_HEIGHT) bytes;
    # the image itself is at bottom right
    # top margin
    yield from (0x00 for i in range((NT_HEIGHT - imgHeight) * NT_WIDTH))
    for y in range(imgHeight):
        yield from (0x00 for i in range(NT_WIDTH - imgWidth))  # left margin
        yield from ntData[y*imgWidth:(y+1)*imgWidth]

    # attribute table (16*15 blocks, 8*8 bytes)
    yield from encode_at_data(16 * 15 * [0b00])

    # offsets for sprite coordinates and background scrolling
    xOffset = (NT_WIDTH  - imgWidth ) * 4
    yOffset = (NT_HEIGHT - imgHeight) * 4

    # sprites (MAX_SPRITES * 4 bytes)
    for (i, (x, y, t)) in enumerate(spriteData):
        yield from (
            yOffset + y * TILE_HEIGHT - 1,  # Y position minus 1
            t * 2 + 1,                      # tile index
            0b00000000,                     # attributes
            xOffset + x * TILE_WIDTH,       # X position
        )
    for i in range(MAX_SPRITES - len(spriteData)):
        yield from (0xff, 0xff, 0xff, 0xff)  # unused (hide)

    # palette (4 bytes)
    yield from outputPal

    # horizontal and vertical background scroll
    yield from (xOffset, yOffset)

def encode_tile(tile):
    # tile: a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    # generate one integer with TILE_WIDTH bits per call
    for bp in range(2):
        for y in range(0, TILE_HEIGHT * TILE_WIDTH, TILE_WIDTH):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (TILE_WIDTH - 1 - x)
                for x in range(TILE_WIDTH)
            )

# --- main --------------------------------------------------------------------

def main():
    (inputFile, outputPal) = parse_arguments()

    # read tiles
    try:
        with open(inputFile, "rb") as handle:
            handle.seek(0)
            image = Image.open(handle)
            imgTiles = list(get_tiles(image))
            imgWidth  = image.width  // TILE_WIDTH
            imgHeight = image.height // TILE_HEIGHT
    except OSError:
        sys.exit("Error reading input file.")

    # what each distinct tile looks like;
    # does not change during elimination of tiles
    origDistinctImgTiles = sorted(set(imgTiles) | set((BLANK_TILE,)))
    origDistinctImgTileCnt = len(origDistinctImgTiles)

    # create a look-up table of distances between any two tiles;
    # does not change during elimination of tiles
    origTileDistances = []
    for tile1 in origDistinctImgTiles:
        for tile2 in origDistinctImgTiles:
            origTileDistances.append(get_tile_distance(tile1, tile2))

    # which tile was originally in each tile position;
    # does not change during elimination of tiles;
    # used for calculating total error
    origImgTileIndexes = [origDistinctImgTiles.index(t) for t in imgTiles]

    # indexes to origDistinctImgTiles (what hasn't been eliminated yet)
    distinctImgTilesLeft = set(range(origDistinctImgTileCnt))

    # updated when a tile is eliminated
    imgTileIndexes = origImgTileIndexes.copy()

    print("Image has {} distinct tiles. Eliminating tiles if needed.".format(
        origDistinctImgTileCnt
    ))
    eliminatedTileCnt = 0

    while True:
        # assign as many image tiles as possible to sprites; the rest will be
        # background tiles
        (bgTileIndexes, spriteData) = assign_tiles_to_sprites(
            imgTileIndexes, imgWidth, imgHeight
        )

        # get number of distinct background tiles
        distinctBgTileCnt = len(set(bgTileIndexes) | set((BLANK_TILE_INDEX,)))

        if distinctBgTileCnt <= MAX_BG_TILES:
            break
        else:
            # replace a tile with one that will cause the smallest total error
            (from_, to_) = get_tile_to_replace(
                origDistinctImgTileCnt, origTileDistances,
                collections.Counter(imgTileIndexes), distinctImgTilesLeft
            )
            eliminatedTileCnt += 1
            distinctImgTilesLeft.remove(from_)
            imgTileIndexes = [
                (to_ if i == from_ else i) for i in imgTileIndexes
            ]

    totalError = sum(
        origTileDistances[t1*origDistinctImgTileCnt+t2]
        for (t1, t2) in zip(origImgTileIndexes, imgTileIndexes)
    )
    # ratio=1 if the entire image changed between darkest and brightest
    totalErrorRatio = (
        totalError / (imgWidth * imgHeight * TILE_WIDTH * TILE_HEIGHT * 3)
    )

    print(
        "{} tiles eliminated with a total error of {} units "
        "({:.0f} parts per million).".format(
            eliminatedTileCnt, totalError, totalErrorRatio * 10**6
        )
    )
    print(
        "Image has {} distinct tiles ({} sprites and {} distinct background "
        "tiles).".format(
            len(distinctImgTilesLeft), len(spriteData), distinctBgTileCnt
        )
    )

    del distinctImgTilesLeft

    # get data of distinct background tiles
    distinctBgTiles = sorted(
        origDistinctImgTiles[i]
        for i in (set(bgTileIndexes) | set((BLANK_TILE_INDEX,)))
    )
    # convert background tile indexes from image-wide to background-wide
    bgTileIndexes = [
        distinctBgTiles.index(origDistinctImgTiles[i]) for i in bgTileIndexes
    ]

    # get data of distinct pairs of sprite tiles
    distinctSprTileIndPairs = set((t1, t2) for (x, y, t1, t2) in spriteData)
    distinctSprTilePairs = sorted(
        (origDistinctImgTiles[t1], origDistinctImgTiles[t2])
        for (t1, t2) in distinctSprTileIndPairs
    )
    del distinctSprTileIndPairs
    # make sprites refer to tile pairs instead of individual tiles
    spriteData = [
        (
            x, y, distinctSprTilePairs.index(
                (origDistinctImgTiles[t1], origDistinctImgTiles[t2])
            )
        ) for (x, y, t1, t2) in spriteData
    ]
    # sort sprites by Y and X
    spriteData.sort(key=lambda s: (s[1], s[0]))

    # write PRG data
    try:
        with open(PRG_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_prg_data(
                bgTileIndexes, spriteData, outputPal, imgWidth, imgHeight
            )))
    except OSError:
        sys.exit(f"Error writing {PRG_OUT_FILE}")
    print(f"Wrote {PRG_OUT_FILE}")

    # combine and pad tile data to (MAX_BG_TILES + MAX_SPRITES * 2) tiles;
    # a tile is a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    tiles = []
    tiles.extend(distinctBgTiles)
    tiles.extend(
        UNUSED_TILE for i in range(MAX_BG_TILES - len(distinctBgTiles))
    )
    tiles.extend(itertools.chain.from_iterable(distinctSprTilePairs))
    tiles.extend(
        UNUSED_TILE
        for i in range((MAX_SPRITES - len(distinctSprTilePairs)) * 2)
    )

    # write CHR data
    try:
        with open(CHR_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(itertools.chain.from_iterable(
                encode_tile(t) for t in tiles
            )))
    except OSError:
        sys.exit(f"Error writing {CHR_OUT_FILE}")
    print(f"Wrote {CHR_OUT_FILE}")

main()
