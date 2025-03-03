# convert an image into NES graphics data

import collections, itertools, os, sys
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow module required. See https://python-pillow.org")

# palette of input image (red, green, blue)
INPUT_PALETTE = (
    (0x00, 0x00, 0x00),
    (0x55, 0x55, 0x55),
    (0xaa, 0xaa, 0xaa),
    (0xff, 0xff, 0xff),
)

# special values to write
BLANK_TILE    = 64 * (0,)  # filled with colour 0
UNUSED_TILE   = 64 * (3,)  # filled with colour 3

# files to write (used by stillimage.asm)
PRG_OUT_FILE = "prg.bin"
CHR_OUT_FILE = "chr.bin"

# the NES can't display more than 8 sprites per scanline or more than 64
# sprites total; decrease these to reserve sprites for other use
MAX_SPRITES_PER_SCANLINE =  8
MAX_TOTAL_SPRITES        = 64

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

def get_prg_data(ntData, spriteData, outputPal, imgWidth, imgHeight):
    # generate each byte of PRG data;
    # ntData:     indexes to distinct background tiles
    # spriteData: (X, Y, index_to_distinct_sprite_pairs) for each
    # outputPal:  a tuple of 4 ints
    # imgWidth:   image width  in tiles
    # imgHeight:  image height in tiles

    # name table (32*30 bytes); the image itself is at bottom right
    yield from (0x00 for i in range((30 - imgHeight) * 32))  # top margin
    for y in range(imgHeight):
        yield from (0x00 for i in range(32 - imgWidth))  # left margin
        yield from ntData[y*imgWidth:(y+1)*imgWidth]

    # attribute table (16*15 blocks, 8*8 bytes)
    yield from encode_at_data(16 * 15 * [0b00])

    # offsets for sprite coordinates and background scrolling
    xOffset = (32 - imgWidth ) * 4
    yOffset = (30 - imgHeight) * 4

    # sprites (64 * 4 bytes)
    for (i, (x, y, t)) in enumerate(spriteData):
        yield from (
            yOffset + y * 8 - 1,  # Y position minus 1
            t * 2 + 1,            # tile index
            0b00000000,           # attributes
            xOffset + x * 8,      # X position
        )
    for i in range(64 - len(spriteData)):
        yield from (0xff, 0xff, 0xff, 0xff)  # unused (hide)

    # palette (8*4 bytes; only BG0 and SPR0 are used)
    for i in range(8):
        yield from outputPal

    # horizontal and vertical background scroll
    yield from (xOffset, yOffset)

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

def assign_tiles_to_sprites(imgTiles, imgWidth, imgHeight):
    # assign as many 1*2-tile pairs as possible to sprites instead;
    # imgTiles:  list of image tiles starting from top left, with duplicates;
    #            each tile is a tuple of 64 2-bit ints
    # imgWidth:  image width  in tiles
    # imgHeight: image height in tiles
    # return:    (background_tiles, sprite_data)

    bgTiles = imgTiles.copy()

    # (x, y, upperSpriteData, lowerSpriteData); unit of x and y: 1*2 tiles
    spriteData = []

    if min(MAX_SPRITES_PER_SCANLINE, MAX_TOTAL_SPRITES) == 0:
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
                    bgTiles[upperTilePos] != BLANK_TILE
                and bgTiles[lowerTilePos] != BLANK_TILE
                and bgTiles.count(bgTiles[upperTilePos]) == 1
                and bgTiles.count(bgTiles[lowerTilePos]) == 1
            ):
                # move tiles from background to sprites
                spriteData.append((
                    sprX, sprY, bgTiles[upperTilePos], bgTiles[lowerTilePos]
                ))
                bgTiles[upperTilePos] = BLANK_TILE
                bgTiles[lowerTilePos] = BLANK_TILE
                spritesPerRow += 1
                if (
                    spritesPerRow == MAX_SPRITES_PER_SCANLINE
                    or len(spriteData) == MAX_TOTAL_SPRITES
                ):
                    break
        if len(spriteData) == MAX_TOTAL_SPRITES:
            break

    return (bgTiles, spriteData)

def get_tile_distance(tile1, tile2):
    # tile1, tile2: tuple of 64 2-bit ints
    return sum(abs(a - b) for (a, b) in zip(tile1, tile2))

def get_tile_to_replace(distinctTiles, tileCounts, minPossibleError=1):
    # which distinct tile to eliminate with the smallest error possible?
    # slow;
    # distinctTiles:    sorted distinct tiles in the image;
    #                   each tile is a tuple of 64 2-bit ints;
    # tileCounts:       {tile_index: count_in_image, ...}
    # minPossibleError: stop searching when the error is this small;
    # return:           tile index to replace: (from, to); from is never 0
    minTotalDiff = -1
    for (fromInd, fromTile) in enumerate(distinctTiles):
        if fromInd > 0:
            # find the closest match for this tile
            minDiff = -1
            for (toInd, toTile) in enumerate(distinctTiles):
                if toInd != fromInd:
                    dist = get_tile_distance(fromTile, toTile)
                    if minDiff == -1 or dist < minDiff:
                        minDiff   = dist
                        bestToInd = toInd
            # remember this tile and its replacement if they result in the
            # smallest total error so far
            totalDiff = minDiff * tileCounts[fromInd]
            if minTotalDiff == -1 or totalDiff < minTotalDiff:
                minTotalDiff     = totalDiff
                bestFromInd      = fromInd
                overallBestToInd = bestToInd
                if minTotalDiff == minPossibleError:
                    break
    return (bestFromInd, overallBestToInd)

def main():
    (inputFile, outputPal) = parse_arguments()

    # read tiles
    try:
        with open(inputFile, "rb") as handle:
            handle.seek(0)
            image = Image.open(handle)
            imgTiles = list(get_tiles(image))
            imgWidth  = image.width  // 8
            imgHeight = image.height // 8
    except OSError:
        sys.exit("Error reading input file.")

    # smallest possible error when replacing tiles
    minTileReplError = 1

    while True:
        distinctImgTiles = sorted(set(imgTiles) | set((BLANK_TILE,)))
        imgTileIndexes = [distinctImgTiles.index(t) for t in imgTiles]

        # assign some background tiles to sprites instead
        (bgTiles, spriteData) = assign_tiles_to_sprites(
            imgTiles, imgWidth, imgHeight
        )
        spriteData.sort(key=lambda s: (s[1], s[0]))  # by Y and X
        distinctSpriteTilePairs = tuple(sorted(set(
            (t1, t2) for (x, y, t1, t2) in spriteData
        )))
        # convert into (x, y, index_to_distinct_sprites)
        spriteData = tuple(
            (x, y, distinctSpriteTilePairs.index((t1, t2)))
            for (x, y, t1, t2) in spriteData
        )

        # get distinct background tiles
        distinctBgTiles = tuple(sorted(set(bgTiles) | set((BLANK_TILE,))))

        print(
            "Image has {} distinct tiles. Need {} sprites and {} distinct "
            "background tiles.".format(
                len(distinctImgTiles), len(spriteData), len(distinctBgTiles)
            )
        )

        if len(distinctBgTiles) <= 256:
            break
        else:
            # replace a tile with one that will cause the smallest total error
            (from_, to_) = get_tile_to_replace(
                distinctImgTiles, collections.Counter(imgTileIndexes),
                minTileReplError
            )
            error = get_tile_distance(
                distinctImgTiles[from_], distinctImgTiles[to_]
            ) * imgTileIndexes.count(from_)
            minTileReplError = max(minTileReplError, error)
            print(f"Eliminating a distinct tile with an error of {error}.")
            imgTiles = [
                distinctImgTiles[to_ if i == from_ else i]
                for i in imgTileIndexes
            ]

    # get name table data (indexes to distinct background tiles)
    ntData = tuple(distinctBgTiles.index(t) for t in bgTiles)

    # write PRG data
    try:
        with open(PRG_OUT_FILE, "wb") as handle:
            handle.seek(0)
            handle.write(bytes(get_prg_data(
                ntData, spriteData, outputPal, imgWidth, imgHeight
            )))
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
