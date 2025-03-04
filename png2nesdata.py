# convert an image into NES graphics data

import collections, itertools, os, sys, time
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

# NES master palette
# key=index, value=(red, green, blue); source: FCEUX (fceux.pal)
# colours omitted (hexadecimal): 0d-0e, 1d-20, 2d-2f, 3d-3f
NES_PALETTE = {
    0x00: (0x74, 0x74, 0x74),  # dark grey
    0x01: (0x24, 0x18, 0x8c),  # x1 = cyan/blue
    0x02: (0x00, 0x00, 0xa8),  # x2 = blue
    0x03: (0x44, 0x00, 0x9c),  # x3 = purple
    0x04: (0x8c, 0x00, 0x74),  # x4 = magenta
    0x05: (0xa8, 0x00, 0x10),  # x5 = magenta/red
    0x06: (0xa4, 0x00, 0x00),  # x6 = red/orange
    0x07: (0x7c, 0x08, 0x00),  # x7 = gold
    0x08: (0x40, 0x2c, 0x00),  # x8 = yellow
    0x09: (0x00, 0x44, 0x00),  # x9 = yellow/green
    0x0a: (0x00, 0x50, 0x00),  # xA = green
    0x0b: (0x00, 0x3c, 0x14),  # xB = green/cyan
    0x0c: (0x18, 0x3c, 0x5c),  # xC = cyan
    0x0f: (0x00, 0x00, 0x00),  # black
    0x10: (0xbc, 0xbc, 0xbc),  # light grey
    0x11: (0x00, 0x70, 0xec),
    0x12: (0x20, 0x38, 0xec),
    0x13: (0x80, 0x00, 0xf0),
    0x14: (0xbc, 0x00, 0xbc),
    0x15: (0xe4, 0x00, 0x58),
    0x16: (0xd8, 0x28, 0x00),
    0x17: (0xc8, 0x4c, 0x0c),
    0x18: (0x88, 0x70, 0x00),
    0x19: (0x00, 0x94, 0x00),
    0x1a: (0x00, 0xa8, 0x00),
    0x1b: (0x00, 0x90, 0x38),
    0x1c: (0x00, 0x80, 0x88),
    0x21: (0x3c, 0xbc, 0xfc),
    0x22: (0x5c, 0x94, 0xfc),
    0x23: (0xcc, 0x88, 0xfc),
    0x24: (0xf4, 0x78, 0xfc),
    0x25: (0xfc, 0x74, 0xb4),
    0x26: (0xfc, 0x74, 0x60),
    0x27: (0xfc, 0x98, 0x38),
    0x28: (0xf0, 0xbc, 0x3c),
    0x29: (0x80, 0xd0, 0x10),
    0x2a: (0x4c, 0xdc, 0x48),
    0x2b: (0x58, 0xf8, 0x98),
    0x2c: (0x00, 0xe8, 0xd8),
    0x30: (0xfc, 0xfc, 0xfc),  # white
    0x31: (0xa8, 0xe4, 0xfc),
    0x32: (0xc4, 0xd4, 0xfc),
    0x33: (0xd4, 0xc8, 0xfc),
    0x34: (0xfc, 0xc4, 0xfc),
    0x35: (0xfc, 0xc4, 0xd8),
    0x36: (0xfc, 0xbc, 0xb0),
    0x37: (0xfc, 0xd8, 0xa8),
    0x38: (0xfc, 0xe4, 0xa0),
    0x39: (0xe0, 0xfc, 0xa0),
    0x3a: (0xa8, 0xf0, 0xbc),
    0x3b: (0xb0, 0xfc, 0xcc),
    0x3c: (0x9c, 0xfc, 0xf0),
}

# files to write (used by stillimage.asm)
PRG_OUT_FILE = "prg.bin"
CHR_OUT_FILE = "chr.bin"

BLANK_TILE_INDEX = 0
BLANK_TILE  = TILE_WIDTH * TILE_HEIGHT * (0,)  # filled with colour 0
UNUSED_TILE = TILE_WIDTH * TILE_HEIGHT * (3,)  # filled with colour 3
UNUSED_COLOUR = 0x00  # NES colour index

# --- input file reading ------------------------------------------------------

def get_colour_diff(rgb1, rgb2):
    # get difference (0-768) of two colours (red, green, blue)
    return sum(abs(comp[0] - comp[1]) for comp in zip(rgb1, rgb2))

def get_closest_nes_colour(rgb):
    # rgb:    colour (red, green, blue)
    # return: closest NES colour index
    minDiff = -1
    for nesColour in sorted(NES_PALETTE):
        diff = get_colour_diff(NES_PALETTE[nesColour], rgb)
        if minDiff == -1 or diff < minDiff:
            minDiff = diff
            bestNesColour = nesColour
    return bestNesColour

def get_colour_conv_table(image):
    # get a dict that converts original colour indexes into NES colour indexes

    # get palette in [R, G, B, ...] format
    imgPal = image.getpalette()
    # convert palette into [(R, G, B), ...] format
    imgPal = [tuple(imgPal[i*3:(i+1)*3]) for i in range(len(imgPal) // 3)]
    # get colours that are actually used, in [(R, G, B), ...] format
    coloursUsed = [imgPal[c[1]] for c in image.getcolors()]

    return dict(
        (imgPal.index(c), get_closest_nes_colour(c)) for c in coloursUsed
    )

def nes_colour_to_brightness(colour):
    (red, green, blue) = NES_PALETTE[colour]
    return red * 2 + green * 3 + blue

def get_tiles(image):
    # generate each tile as a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints

    for y in range(0, image.height, TILE_HEIGHT):
        for x in range(0, image.width, TILE_WIDTH):
            yield tuple(
                image.crop((x, y, x + TILE_WIDTH, y + TILE_HEIGHT)).getdata()
            )

def read_image(image):
    # return a tuple with:
    #     image_tiles (pixels of each tile with duplicates;
    #                 pixels are indexes to nes_palette)
    #     nes_palette (4 NES colour indexes)
    #     image_width_in_tiles

    # validate image
    if not 8 <= image.width <= 256 or image.width % 8 > 0:
        sys.exit("Image width must be 8-256 and a multiple of 8.")
    if not 8 <= image.height <= 224 or image.height % 8 > 0:
        sys.exit("Image height must be 8-224 and a multiple of 8.")
    if image.getcolors(4) is None:
        sys.exit("The image must have 4 colours or less.")

    # convert image into indexed colour
    if image.mode != "P":
        image = image.convert(
            "P", dither=Image.Dither.NONE, palette=Image.Palette.ADAPTIVE
        )

    # {original_colour_index: closest_nes_colour_index, ...}
    imgColourToNesColour = get_colour_conv_table(image)
    if len(set(imgColourToNesColour.values())) < len(imgColourToNesColour):
        sys.exit(
            "Error: two or more image colours correspond to the same NES "
            "colour. Try making the image colours more distinct."
        )

    # create output palette (NES colour indexes) sorted by brightness
    # and pad it to 4 colours
    nesPalette = sorted(imgColourToNesColour.values())
    nesPalette.sort(key=lambda c: nes_colour_to_brightness(c))
    nesPalette.extend((4 - len(nesPalette)) * (UNUSED_COLOUR,))

    # {original_colour_index: index_to_nesPalette, ...}
    imgColourToNesColour = dict(
        (i, nesPalette.index(imgColourToNesColour[i]))
        for i in imgColourToNesColour
    )

    # get pixels of tiles and convert their colours to indexes to nesPalette
    imgTiles = [
        tuple(imgColourToNesColour[c] for c in t)
        for t in get_tiles(image)
    ]

    return (imgTiles, nesPalette, image.width // TILE_WIDTH)

# --- graphics data processing ------------------------------------------------

def get_tile_distance(tile1, tile2):
    # tile1, tile2: tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    return sum(abs(a - b) for (a, b) in zip(tile1, tile2))

def assign_tiles_to_sprites(imgTiles, imgWidth, imgHeight):
    # assign as many 1*2-tile pairs as possible to sprites;
    # the rest will be background tiles
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
                       spritesPerRow   == MAX_SPRITES_PER_SCANLINE
                    or len(spriteData) == MAX_SPRITES
                ):
                    break
        if len(spriteData) == MAX_SPRITES:
            break

    return (bgTiles, spriteData)

def get_tile_to_replace(
    origTileCnt, tileDistances, tileCnts, distinctTilesLeft, minPossibleError=1
):
    # which distinct tile to eliminate with the smallest error possible?
    #   origTileCnt:       original number of distinct tiles
    #   tileDistances:     a table of distances between tiles;
    #                      index: (tile_index1 * origTileCnt + tile_index2)
    #   tileCnts:          {tile_index: count_in_image, ...}
    #   distinctTilesLeft: set of indexes to original distinct tiles
    #   minPossibleError:  an int; stop when the total error is this small,
    #                      for speed
    #   return:            tile to replace: (from_index, to_index)

    # find a tile pair that minimises
    # (distance_between_tiles * source_tile_count);
    # it seems it would not help at all to prefer target tiles that are common

    minTotalDiff = -1

    for srcInd in distinctTilesLeft:
        if srcInd != BLANK_TILE_INDEX:
            # find the closest match for this tile
            minDiff = -1
            for dstInd in distinctTilesLeft:
                if dstInd != srcInd:
                    diff = tileDistances[srcInd*origTileCnt+dstInd]
                    if minDiff == -1 or diff < minDiff:
                        minDiff    = diff
                        bestDstInd = dstInd
            # remember this tile and its replacement if they result in the
            # smallest total error so far
            totalDiff = minDiff * tileCnts[srcInd]
            if minTotalDiff == -1 or totalDiff < minTotalDiff:
                minTotalDiff      = totalDiff
                bestSrcInd        = srcInd
                overallBestDstInd = bestDstInd
                if minTotalDiff == minPossibleError:
                    break

    return (bestSrcInd, overallBestDstInd)

def eliminate_tiles(origDistinctImgTiles, origImgTileIndexes, imgWidth):
    # if there are too many distinct tiles in the image, eliminate them
    # origDistinctImgTiles: pixels of each originally distinct tile;
    #                       does not change
    # origImgTileIndexes:   which tile index was originally in each tile
    #                       position; does not change
    # imgWidth:             image width in tiles
    # return:               new tile indexes in each tile position

    imgHeight = len(origImgTileIndexes) // imgWidth  # image height in tiles

    # a table of distances between any two tiles; does not change
    origTileDistances = []
    for tile1 in origDistinctImgTiles:
        for tile2 in origDistinctImgTiles:
            origTileDistances.append(get_tile_distance(tile1, tile2))

    # which tile index is in each tile position;
    # updated whenever a tile is eliminated
    imgTileIndexes = origImgTileIndexes.copy()

    # indexes to origDistinctImgTiles;
    # tells us which tiles haven't been eliminated yet
    distinctImgTilesLeft = set(range(len(origDistinctImgTiles)))

    # the smallest possible error on each round of tile elimination;
    # it never decreases, so it lets us stop searching early for a ~30% speedup
    # and no loss of quality
    minPossibleError = 1

    while True:
        # assign remaining image tiles to sprites and background
        (bgTileIndexes, spriteData) = assign_tiles_to_sprites(
            imgTileIndexes, imgWidth, imgHeight
        )

        # get number of distinct background tiles
        distinctBgTileCnt = len(set(bgTileIndexes) | set((BLANK_TILE_INDEX,)))

        if distinctBgTileCnt <= MAX_BG_TILES:
            break
        else:
            # replace a tile with one that will cause the smallest total error
            (from_, to_) = get_tile_to_replace(  # TODO: inline?
                len(origDistinctImgTiles),
                origTileDistances,
                collections.Counter(imgTileIndexes),
                distinctImgTilesLeft,
                minPossibleError
            )
            minPossibleError = max(
                minPossibleError,
                origTileDistances[from_*len(origDistinctImgTiles)+to_]
                * imgTileIndexes.count(from_)
            )

            imgTileIndexes = [
                (to_ if i == from_ else i) for i in imgTileIndexes
            ]
            distinctImgTilesLeft.remove(from_)

    return imgTileIndexes

# --- output data encoding ----------------------------------------------------

def encode_at_data(atData):
    # encode attribute table data
    # atData:   a list of 240 (16*15) 2-bit ints
    # generate: 64 8-bit ints

    # pad to 16*16 attribute blocks (last row unused by the NES)
    atData.extend(0b00 for i in range(16 * 16 - len(atData)))

    for y in range(8):
        for x in range(8):
            srcInd = (y * 16 + x) * 2
            yield (
                   atData[srcInd     ]
                | (atData[srcInd+   1] << 2)
                | (atData[srcInd+16  ] << 4)
                | (atData[srcInd+16+1] << 6)
            )

def get_prg_data(ntData, spriteData, nesPalette, imgWidth):
    # generate each byte of PRG data;
    # ntData:     indexes to distinct background tiles
    # spriteData: (X, Y, index_to_distinct_sprite_pairs) for each
    # nesPalette: a tuple of 4 ints
    # imgWidth:   image width in tiles

    imgHeight = len(ntData) // imgWidth

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
    yield from nesPalette

    # horizontal and vertical background scroll
    yield from (xOffset, yOffset)

def get_output_tiles(bgTiles, sprTilePairs):
    # bgTiles:      list of distinct           background tiles
    # sprTilePairs: list of distinct tuples of sprite     tiles
    # generate:     (MAX_BG_TILES + MAX_SPRITES * 2) tiles
    # (a tile is a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints)
    yield from bgTiles
    yield from (UNUSED_TILE for i in range(MAX_BG_TILES - len(bgTiles)))
    yield from itertools.chain.from_iterable(sprTilePairs)
    yield from (
        UNUSED_TILE for i in range((MAX_SPRITES - len(sprTilePairs)) * 2)
    )

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
    startTime = time.time()

    # parse command line argument
    if len(sys.argv) != 2:
        sys.exit(
            "Converts an image into NES graphics data. Argument: input file. "
            "See README.md for details."
        )
    inputFile = sys.argv[1]
    if not os.path.isfile(inputFile):
        sys.exit("Input file not found.")

    # read input file
    try:
        with open(inputFile, "rb") as handle:
            handle.seek(0)
            image = Image.open(handle)
            (imgTiles, nesPalette, imgWidth) = read_image(image)
    except OSError:
        sys.exit("Error reading input file.")

    imgHeight = len(imgTiles) // imgWidth

    print("NES palette to use for {}: {}".format(
        os.path.basename(inputFile), " ".join(f"0x{c:02x}" for c in nesPalette)
    ))

    # pixels of each originally distinct tile;
    # does not change during elimination of tiles
    origDistinctImgTiles = sorted(set(imgTiles) | set((BLANK_TILE,)))

    # which tile index was originally in each tile position;
    # does not change during elimination of tiles;
    # used for calculating total error
    origImgTileIndexes = [origDistinctImgTiles.index(t) for t in imgTiles]

    print(f"The image has {len(origDistinctImgTiles)} distinct tiles.")

    # eliminate distinct tiles if necessary
    imgTileIndexes = eliminate_tiles(
        origDistinctImgTiles, origImgTileIndexes, imgWidth
    )

    # reassign remaining image tiles to sprites and background
    (bgTileIndexes, spriteData) = assign_tiles_to_sprites(
        imgTileIndexes, imgWidth, imgHeight
    )

    distinctBgTileIndexes = set(bgTileIndexes) | set((BLANK_TILE_INDEX,))
    if (
           len(distinctBgTileIndexes) > MAX_BG_TILES
        or len(spriteData)            > MAX_SPRITES
    ):
        sys.exit("Error: a crosscheck failed (this should never happen).")

    # get the error caused by eliminating tiles
    totalError = sum(
        get_tile_distance(origDistinctImgTiles[t1], origDistinctImgTiles[t2])
        for (t1, t2) in zip(origImgTileIndexes, imgTileIndexes)
    )
    del origImgTileIndexes
    if totalError > 0:
        # an error of 100% means the whole image changed between the darkest
        # and the lightest colour
        print(
            "The number of distinct tiles was reduced to {}, making the image "
            "quality {:.2f}% worse.".format(
                len(set(imgTileIndexes) | set((BLANK_TILE_INDEX,))),
                totalError /
                (imgWidth * imgHeight * TILE_WIDTH * TILE_HEIGHT * 3) * 100
            )
        )

    print(
        "The NES program will have {} distinct background tiles and {} "
        "sprites.".format(len(distinctBgTileIndexes), len(spriteData))
    )

    # get pixels of distinct background tiles;
    # primary sort by number of colours, secondary sort by pixels
    distinctBgTiles = sorted(
        origDistinctImgTiles[i] for i in distinctBgTileIndexes
    )
    distinctBgTiles.sort(key=lambda t: len(set(t)))
    # convert background tile indexes from image-wide to background-wide
    bgTileIndexes = [
        distinctBgTiles.index(origDistinctImgTiles[i]) for i in bgTileIndexes
    ]
    del distinctBgTileIndexes

    # get pixels of distinct pairs of sprite tiles;
    # primary sort by number of colours, secondary sort by pixels
    distinctSprTileIndPairs = set((t1, t2) for (x, y, t1, t2) in spriteData)
    distinctSprTilePairs = sorted(
        (origDistinctImgTiles[t1], origDistinctImgTiles[t2])
        for (t1, t2) in distinctSprTileIndPairs
    )
    distinctSprTilePairs.sort(key=lambda p: len(set(p[0]) | set(p[1])))
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

    # TODO: deduplicate sprite tile pair data by flipping?

    # write PRG data
    try:
        with open(PRG_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_prg_data(
                bgTileIndexes, spriteData, nesPalette, imgWidth
            )))
    except OSError:
        sys.exit(f"Error writing {PRG_OUT_FILE}")

    # write CHR data
    try:
        with open(CHR_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(itertools.chain.from_iterable(
                encode_tile(t) for t in get_output_tiles(
                    distinctBgTiles, distinctSprTilePairs
                )
            )))
    except OSError:
        sys.exit(f"Error writing {CHR_OUT_FILE}")

    print("Wrote {} and {}. Total time: {:.1f} seconds.".format(
        PRG_OUT_FILE, CHR_OUT_FILE, time.time() - startTime
    ))

main()
