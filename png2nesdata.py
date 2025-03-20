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

# --- read_image() and its functions ------------------------------------------

def get_colour_diff(rgb1, rgb2):
    # get difference (0-1536) of two colours (red, green, blue)
    return (
          2 * abs(rgb1[0] - rgb2[0])
        + 3 * abs(rgb1[1] - rgb2[1])
        +     abs(rgb1[2] - rgb2[2])
    )

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

def colour_to_brightness(rgb):
    # get brightness (0-1536) of colour (red, green, blue)
    return 2 * rgb[0] + 3 * rgb[1] + rgb[2]

def get_tiles(image):
    # generate each tile as a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints

    for y in range(0, image.height, TILE_HEIGHT):
        for x in range(0, image.width, TILE_WIDTH):
            yield tuple(
                image.crop((x, y, x + TILE_WIDTH, y + TILE_HEIGHT)).getdata()
            )

def read_image(image):
    # return: (image_tiles, nes_palette, image_width_in_tiles);
    #   image_tiles: pixels of each tile with duplicates;
    #                pixels are indexes to nes_palette
    #   nes_palette: 4 NES colour indexes

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
    nesPalette.sort(key=lambda c: colour_to_brightness(NES_PALETTE[c]))
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

# --- eliminate_and_assign_tiles() and its functions --------------------------

def get_tile_diff(tile1, tile2, nesPalette):
    # tile1, tile2: tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    return sum(
        get_colour_diff(
            NES_PALETTE[nesPalette[c1]], NES_PALETTE[nesPalette[c2]]
        ) for (c1, c2) in zip(tile1, tile2)
    )

def assign_tiles_to_sprites(imgTiles, imgWidth, imgHeight):
    # assign as many 1*2-tile pairs as possible to sprites
    #   imgTiles:  list of image tile indexes starting from top left, with
    #              duplicates
    #   imgWidth:  image width  in tiles
    #   imgHeight: image height in tiles
    #   generate:  sprite data: (x, y, upper_sprite, lower_sprite) per call;
    #              x, y are in tiles;
    #              upper_sprite, lower_sprite are image tile indexes

    # tiles used exactly once, excluding the blank tile
    cntr = collections.Counter(imgTiles)
    uniqueTiles = set(
        t for t in cntr if t != BLANK_TILE_INDEX and cntr[t] == 1
    )

    spriteCnt = 0  # number of sprites assigned so far

    # replace 1*2-tile pairs where both tiles are non-blank and unique within
    # the image; this way each sprite saves 2 background tiles;
    # if the height is odd, don't bother looking at the last row
    for sprY in range(0, imgHeight - 1, 2):
        rowSpriteCnt = 0  # number of sprites assigned on this row
        for sprX in range(imgWidth):
            upperTilePos =  sprY      * imgWidth + sprX
            lowerTilePos = (sprY + 1) * imgWidth + sprX
            if (
                    imgTiles[upperTilePos] in uniqueTiles
                and imgTiles[lowerTilePos] in uniqueTiles
            ):
                # assign tile to sprites
                yield (
                    sprX, sprY, imgTiles[upperTilePos], imgTiles[lowerTilePos]
                )
                rowSpriteCnt += 1
                spriteCnt    += 1
                if (
                       rowSpriteCnt == MAX_SPRITES_PER_SCANLINE
                    or spriteCnt    == MAX_SPRITES
                ):
                    break
        if spriteCnt == MAX_SPRITES:
            break

def get_tile_to_replace(
    origTileCnt, tileDiffs, tileCnts, distinctTilesLeft, minPossibleError=1
):
    # which distinct tile to eliminate with the smallest error possible?
    #   origTileCnt:       original number of distinct tiles
    #   tileDiffs:         a table of differences between tiles;
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
                    diff = tileDiffs[srcInd*origTileCnt+dstInd]
                    if minDiff == -1 or diff < minDiff:
                        minDiff = diff
            # remember this tile if it results in the smallest total error so
            # far
            totalDiff = minDiff * tileCnts[srcInd]
            if minTotalDiff == -1 or totalDiff < minTotalDiff:
                minTotalDiff = totalDiff
                bestSrcInd   = srcInd
                if minTotalDiff == minPossibleError:
                    break

    # find the closest match for the source tile again
    minDiff = -1
    for dstInd in distinctTilesLeft:
        if dstInd != bestSrcInd:
            diff = tileDiffs[bestSrcInd*origTileCnt+dstInd]
            if minDiff == -1 or diff < minDiff:
                minDiff = diff
                bestDstInd = dstInd

    return (bestSrcInd, bestDstInd)

def get_tile_diff(tile1, tile2, nesPalette):
    # get difference of two tiles
    #   tile1, tile2: tuple of TILE_WIDTH * TILE_HEIGHT ints
    #   nesPalette:   list of NES colour indexes
    return sum(
        get_colour_diff(
            NES_PALETTE[nesPalette[c1]], NES_PALETTE[nesPalette[c2]]
        ) for (c1, c2) in zip(tile1, tile2)
    )

def eliminate_tiles(
    origDistinctImgTiles, origImgTileIndexes, imgWidth, nesPalette
):
    # if there are too many distinct tiles in the image, eliminate them
    #   origDistinctImgTiles: pixels of each originally distinct tile;
    #                         does not change
    #   origImgTileIndexes:   which tile index was originally in each tile
    #                         position; does not change
    #   imgWidth:             image width in tiles
    #   nesPalette:           list of NES colour indexes
    #   return:               new tile indexes in each tile position

    imgHeight = len(origImgTileIndexes) // imgWidth  # image height in tiles

    # a table of differences between any two tiles; does not change
    origTileDiffs = []
    for tile1 in origDistinctImgTiles:
        for tile2 in origDistinctImgTiles:
            origTileDiffs.append(get_tile_diff(tile1, tile2, nesPalette))

    # which tile index is in each tile position; updated whenever a tile is
    # eliminated
    imgTileIndexes = origImgTileIndexes.copy()

    # indexes to origDistinctImgTiles; tells us which tiles haven't been
    # eliminated yet
    distinctImgTilesLeft = set(range(len(origDistinctImgTiles)))

    # the smallest possible error on each round of tile elimination;
    # it never decreases, so it lets us stop searching early for a ~30% speedup
    # and no loss of quality
    minPossibleError = 1

    while True:
        # get number of distinct background tiles
        spriteCnt = len(list(
            assign_tiles_to_sprites(imgTileIndexes, imgWidth, imgHeight)
        ))
        distinctBgTileCnt = (
            len(set(imgTileIndexes) | set((BLANK_TILE_INDEX,))) - spriteCnt * 2
        )

        if distinctBgTileCnt <= MAX_BG_TILES:
            break
        else:
            # replace a tile with one that will cause the smallest total error
            (tileFrom, tileTo) = get_tile_to_replace(
                len(origDistinctImgTiles),
                origTileDiffs,
                collections.Counter(imgTileIndexes),
                distinctImgTilesLeft,
                minPossibleError
            )
            minPossibleError = max(
                minPossibleError,
                origTileDiffs[tileFrom*len(origDistinctImgTiles)+tileTo]
                * imgTileIndexes.count(tileFrom)
            )

            imgTileIndexes = [
                (tileTo if i == tileFrom else i) for i in imgTileIndexes
            ]
            distinctImgTilesLeft.remove(tileFrom)

    return imgTileIndexes

def eliminate_and_assign_tiles(
    origDistinctImgTiles, imgTiles, imgWidth, nesPalette
):
    # eliminate distinct tiles if necessary and assign tiles to background and
    # sprites
    #   origDistinctImgTiles: pixels of each originally distinct tile
    #   imgTiles:             pixels of each tile with duplicates
    #   imgWidth:             image width in tiles
    #   nesPalette:           list of NES colour indexes
    #   return:               (background_tile_indexes, sprite_data,
    #                         total_error);
    #                           sprite_data: [(x, y, i1, i2), ...]
    #                           total_error: int

    imgHeight = len(imgTiles) // imgWidth

    # which tile index was originally in each tile position
    origImgTileIndexes = [origDistinctImgTiles.index(t) for t in imgTiles]

    # eliminate distinct tiles if necessary
    imgTileIndexes = eliminate_tiles(
        origDistinctImgTiles, origImgTileIndexes, imgWidth, nesPalette
    )

    # reassign as many tiles as possible to sprites
    spriteData = list(assign_tiles_to_sprites(
        imgTileIndexes, imgWidth, imgHeight
    ))

    # mark background tiles behind sprites as blank
    bgTileIndexes = imgTileIndexes.copy()
    for (x, y, t1, t2) in spriteData:
        bgTileIndexes[ y   *imgWidth+x] = BLANK_TILE_INDEX
        bgTileIndexes[(y+1)*imgWidth+x] = BLANK_TILE_INDEX

    distinctBgTileIndexes = set(bgTileIndexes) | set((BLANK_TILE_INDEX,))
    if (
           len(distinctBgTileIndexes) > MAX_BG_TILES
        or len(spriteData)            > MAX_SPRITES
    ):
        sys.exit("Error: crosscheck #1 failed (this should never happen).")

    # get the error caused by eliminating tiles
    totalError = sum(
        get_tile_diff(
            origDistinctImgTiles[t1], origDistinctImgTiles[t2], nesPalette
        ) for (t1, t2) in zip(origImgTileIndexes, imgTileIndexes)
    )

    return (bgTileIndexes, spriteData, totalError)

# -----------------------------------------------------------------------------

def process_background_data(origDistinctImgTiles, bgTileIndexes):
    # return: (distinct_background_tiles, background_tiles);
    #         background_tiles are indexes to distinct_background_tiles

    # get pixels of distinct background tiles;
    # primary sort by number of colours, secondary sort by pixels
    distinctBgTiles = sorted(
        origDistinctImgTiles[i] for i in (
            set(bgTileIndexes) | set((BLANK_TILE_INDEX,))
        )
    )
    distinctBgTiles.sort(key=lambda t: len(set(t)))

    # convert background tile indexes from image-wide to background-wide
    bgTileIndexes = [
        distinctBgTiles.index(origDistinctImgTiles[i]) for i in bgTileIndexes
    ]

    return (distinctBgTiles, bgTileIndexes)

# --- process_sprite_data() and its functions ---------------------------------

def tile_hflip(tile):
    # mirror a tile horizontally (left becomes right)
    #   tile:   a list of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    #   return: new tile
    newTile = []
    for srcY in range(TILE_HEIGHT):
        for srcX in range(TILE_WIDTH):
            srcPos = srcY * TILE_WIDTH + (TILE_WIDTH - 1 - srcX)
            newTile.append(tile[srcPos])
    return tuple(newTile)

def tile_vflip(tile):
    # mirror a tile vertically (top becomes bottom)
    #   tile:   a list of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    #   return: new tile
    newTile = []
    for srcY in range(TILE_HEIGHT):
        for srcX in range(TILE_WIDTH):
            srcPos = (TILE_HEIGHT - 1 - srcY) * TILE_WIDTH + srcX
            newTile.append(tile[srcPos])
    return tuple(newTile)

def deduplicate_sprite_tile_pairs(tilePairs):
    # deduplicate sprite tile pairs by checking if they're horizontal and/or
    # vertical flips of each other;
    #   tilePairs:  list of distinct (tile1, tile2);
    #               a tile is a list of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    #   generate:   tile pairs without duplicates

    for (ind1, (upperTile1, lowerTile1)) in enumerate(tilePairs):
        # find the smallest index where the tile pair is a duplicate of this pair
        smallestInd = ind1

        # any hflips at any index smaller than this one?
        for (ind2, (upperTile2, lowerTile2)) in enumerate(tilePairs[:smallestInd]):
            if (
                    upperTile1 == tile_hflip(upperTile2)
                and lowerTile1 == tile_hflip(lowerTile2)
            ):
                smallestInd = ind2
                break
        # any vflips at even smaller indexes?
        for (ind2, (upperTile2, lowerTile2)) in enumerate(tilePairs[:smallestInd]):
            if (
                    upperTile1 == tile_vflip(lowerTile2)
                and lowerTile1 == tile_vflip(upperTile2)
            ):
                smallestInd = ind2
                break
        # any hflips & vflips at even smaller indexes?
        for (ind2, (upperTile2, lowerTile2)) in enumerate(tilePairs[:smallestInd]):
            if (
                    upperTile1 == tile_hflip(tile_vflip(lowerTile2))
                and lowerTile1 == tile_hflip(tile_vflip(upperTile2))
            ):
                smallestInd = ind2
                break

        # if no flipwise duplicates found, keep this tile pair
        if smallestInd == ind1:
            yield (upperTile1, lowerTile1)

def get_spr_tile_pair_index(upperTile1, lowerTile1, tilePairs):
    # convert a sprite's tile pair from pixel data to indexes to flipwise
    # distinct tile pairs
    #   tilePairs:  list of pixels of distinct sprite tile pairs without flipwise
    #               duplicates
    #   upperTile1: pixels of upper sprite tile
    #   lowerTile1: pixels of lower sprite tile
    #   return:     (index_to_tilePairs, h_flip, v_flip);
    #               h_flip, v_flip: 0=no, 1=yes

    for (ind, (upperTile2, lowerTile2)) in enumerate(tilePairs):
        if (upperTile1, lowerTile1) == (
            upperTile2, lowerTile2
        ):
            return (ind, 0, 0)
        elif (upperTile1, lowerTile1) == (
            tile_hflip(upperTile2), tile_hflip(lowerTile2)
        ):
            return (ind, 1, 0)
        elif (upperTile1, lowerTile1) == (
            tile_vflip(lowerTile2), tile_vflip(upperTile2)
        ):
            return (ind, 0, 1)
        elif (upperTile1, lowerTile1) == (
            tile_hflip(tile_vflip(lowerTile2)),
            tile_hflip(tile_vflip(upperTile2))
        ):
            return (ind, 1, 1)

    sys.exit("Error: crosscheck #2 failed (this should never happen).")

def process_sprite_data(distinctImgTiles, spriteData):
    # convert sprites to flipwise-deduplicated tile pairs
    #   distinctImgTiles: pixels of each distinct tile in the original image
    #   spriteData:       for each sprite: (x, y, tile1, tile2);
    #                       x, y: in tiles;
    #                       tile1, tile2: indexes to distinctImgTiles
    #   return:           (distinct_sprite_tile_pairs, new_sprite_data);
    #                       distinct_sprite_tile_pairs: a list of pairs
    #                         of tuples of pixels;
    #                       new_sprite_data: [(x, y, index, hFlip, vFlip), ...]

    # get pixels of distinct pairs of sprite tiles;
    # primary sort by number of colours, secondary sort by pixels
    distinctIndPairs = set((t1, t2) for (x, y, t1, t2) in spriteData)
    distinctTilePairs = sorted(
        (distinctImgTiles[t1], distinctImgTiles[t2])
        for (t1, t2) in distinctIndPairs
    )
    distinctTilePairs.sort(key=lambda p: len(set(p[0]) | set(p[1])))
    del distinctIndPairs

    # deduplicate tile pairs flipwise
    distinctTilePairs = list(deduplicate_sprite_tile_pairs(distinctTilePairs))

    # reformat sprite data: refer to flipwise-deduplicated tile pairs and store
    # flips
    newSpriteData = []
    for (x, y, t1, t2) in spriteData:
        (tileInd, hFlip, vFlip) = get_spr_tile_pair_index(
            distinctImgTiles[t1], distinctImgTiles[t2], distinctTilePairs
        )
        newSpriteData.append((x, y, tileInd, hFlip, vFlip))

    # sort sprites by Y and X
    newSpriteData.sort(key=lambda s: (s[1], s[0]))

    return (distinctTilePairs, newSpriteData)

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
    # spriteData: (X, Y, index_to_distinct_sprite_pairs, hFlip, vFlip) for each
    # nesPalette: a tuple of 4 ints
    # imgWidth:   image width in tiles

    imgHeight = len(ntData) // imgWidth

    # name table; (NT_WIDTH * NT_HEIGHT) bytes;
    # the image itself is at bottom right
    # top margin
    yield from (
        BLANK_TILE_INDEX for i in range((NT_HEIGHT - imgHeight) * NT_WIDTH)
    )
    for y in range(imgHeight):
        # left margin
        yield from (BLANK_TILE_INDEX for i in range(NT_WIDTH - imgWidth))
        yield from ntData[y*imgWidth:(y+1)*imgWidth]

    # attribute table (16*15 blocks, 8*8 bytes)
    yield from encode_at_data(16 * 15 * [0b00])

    # offsets for sprite coordinates and background scrolling
    xOffset = (NT_WIDTH  - imgWidth ) * 4
    yOffset = (NT_HEIGHT - imgHeight) * 4

    # sprites (MAX_SPRITES * 4 bytes)
    for (x, y, tileInd, hFlip, vFlip) in spriteData:
        yield from (
            yOffset + y * TILE_HEIGHT - 1,  # Y position minus 1
            tileInd * 2 + 1,                # tile index
            (vFlip << 7) | (hFlip << 6),    # attributes
            xOffset + x * TILE_WIDTH,       # X position
        )
    for i in range(MAX_SPRITES - len(spriteData)):
        yield from (0xff, 0xff, 0xff, 0xff)  # unused (hide)

    # palette (4 bytes)
    yield from nesPalette

    # horizontal and vertical background scroll
    yield from (xOffset, yOffset)

def get_output_tiles(bgTiles, sprTilePairs):
    # combine and pad background and sprite tiles;
    # a tile is a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    #   bgTiles:      list of distinct           background tiles
    #   sprTilePairs: list of distinct tuples of sprite     tiles
    #   generate:     (MAX_BG_TILES + MAX_SPRITES * 2) tiles

    yield from bgTiles
    yield from (
        UNUSED_TILE for i in range(MAX_BG_TILES - len(bgTiles))
    )
    yield from itertools.chain.from_iterable(sprTilePairs)
    yield from (
        UNUSED_TILE for i in range((MAX_SPRITES - len(sprTilePairs)) * 2)
    )

def encode_tile(tile):
    # encode a tile into NES format
    #   tile:     a tuple of (TILE_WIDTH * TILE_HEIGHT) 2-bit ints
    #   generate: one integer with TILE_WIDTH bits per call

    for bp in range(2):
        for y in range(0, TILE_HEIGHT * TILE_WIDTH, TILE_WIDTH):
            yield sum(
                ((tile[y+x] >> bp) & 1) << (TILE_WIDTH - 1 - x)
                for x in range(TILE_WIDTH)
            )

# -----------------------------------------------------------------------------

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

    print("Input file: {}, {}*{} tiles, {} distinct tiles".format(
        os.path.basename(inputFile), imgWidth, imgHeight, len(set(imgTiles))
    ))

    # pixels of each originally distinct tile; does not change during
    # elimination of tiles; blank tile needed for margins and behind sprites
    origDistinctImgTiles = sorted(set(imgTiles) | set((BLANK_TILE,)))

    elimStartTime = time.time()
    (bgTileIndexes, spriteData, totalError) = eliminate_and_assign_tiles(
        origDistinctImgTiles, imgTiles, imgWidth, nesPalette
    )
    if totalError > 0:
        maxError = imgWidth * imgHeight * TILE_WIDTH * TILE_HEIGHT * 1536
        print(
            "The number of distinct tiles was reduced (quality loss {:.2f}%, "
            "time {:.1f} s)".format(
                totalError / maxError * 100, time.time() - elimStartTime
            )
        )
    print(
        "Using {} distinct background tiles, {} sprites, NES palette {}"
        .format(
            len(set(bgTileIndexes) | set((BLANK_TILE_INDEX,))),
            len(spriteData), " ".join(f"0x{c:02x}" for c in nesPalette)
        )
    )

    (distinctBgTiles, bgTileIndexes) = process_background_data(
        origDistinctImgTiles, bgTileIndexes
    )
    (distinctSprTilePairs, spriteData) = process_sprite_data(
        origDistinctImgTiles, spriteData
    )

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

    print("Wrote {} and {} (total time {:.1f} s)".format(
        PRG_OUT_FILE, CHR_OUT_FILE, time.time() - startTime
    ))

main()
