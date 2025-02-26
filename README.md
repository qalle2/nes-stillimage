# nes-stillimage

Table of contents:
* [Introduction](#introduction)
* [How to use](#how-to-use)
* [Technical info on the NES program](#technical-info-on-the-nes-program)
* [Sources of images](#sources-of-images)

## Introduction
Two programs:
* `png2chr.py`: A Python program that converts an image (e.g. PNG) into NES graphics data. Requires the [Pillow](https://python-pillow.org) module.
* `stillimage.asm`: An NES program that displays the converted graphics data (assembles with [ASM6](https://www.romhacking.net/utilities/674/)).

Examples (screenshots from FCEUX):

![shareware DOS Doom title screen](snap-doom.png)
![ethically sourced Lena](snap-lena.png)

## How to use
1. get an image file: 192&times;128 pixels, up to 4 colours (`#000000`, `#555555`, `#aaaaaa`, `#ffffff`); there are examples under `test-in/`
1. write NES graphics data to `chr.bin`: `python3 png2chr.py image.png chr.bin`
1. write output palette to `palette.asm`: e.g. `echo "hex 0f 15 26 30" > palette.asm`
1. assemble: `asm6 stillimage.asm stillimage.nes`
1. run `stillimage.nes` in an NES emulator

See also `test.sh` (warning: it deletes files).

## Technical info on the NES program
* PRG ROM: 16 KiB
* CHR ROM: 8 KiB
* mapper: NROM (iNES mapper number 0)
* name table mirroring: vertical
* no raster effects
* max. 4 colours on screen
* sprite size: 8&times;16 pixels
* the NT is scrolled 8 pixels upwards to centre the image vertically
* the image itself:
  * size: 24&times;16 tiles = 192&times;128 pixels
  * location: NT tile positions (4,8)&ndash;(27,23) and AT blocks (2,4)&ndash;(13,11)
* left & middle third of image:
  * made of background tiles
  * size: 16&times;16 tiles = 128&times;128 pixels
  * location: NT tile positions (4,8)&ndash;(19,23) and AT blocks (2,4)&ndash;(9,11)
  * uses background subpalette 0
  * no sprites
* right third of image:
  * made of sprites using subpalette 0
  * size: 8&times;8 sprites = 8&times;16 tiles = 64&times;128 pixels
  * location: equivalent to NT tile positions (20,8)&ndash;(27,23) (but remember that the NT has been vertically scrolled)
  * background: any tiles; uses subpalette 1
* margins:
  * background: any tiles; uses subpalette 1
  * no sprites
* palettes:
  * background palette 0: the colours of the image itself
  * background palette 1: filled with the first colour of background palette 0
  * sprite palette 0: same as background palette 0

## Sources of images
* `doom.png`: shareware version of *Doom* by id Software
* `lena.png`: [Ethically sourced Lena picture](https://mortenhannemose.github.io/lena/) by Morten Hannemose

