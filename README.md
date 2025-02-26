# nes-stillimage

Table of contents:
* [Introduction](#introduction)
* [png2nesdata.py](#png2nesdatapy)
* [stillimage.asm](#stillimageasm)
* [Technical info on the NES program](#technical-info-on-the-nes-program)
* [Sources of images](#sources-of-images)

## Introduction
Two programs that let you convert an image (e.g. PNG) into an NES ROM that shows the image.

Examples (screenshots from FCEUX):

![shareware DOS Doom title screen](snap-doom.png)
![ethically sourced Lena](snap-lena.png)

## png2nesdata.py
A Python program that converts an image (e.g. PNG) into NES graphics data. Requires the [Pillow](https://python-pillow.org) module.

Command line arguments: *inputFile outputColour0 outputColour1 outputColour2 outputColour3*
* *inputFile*: the image file to read:
  * size: exactly 192&times;128 pixels (24&times;16 NES tiles)
  * may only contain these colours (hexadecimal RRGGBB): `000000`, `555555`, `aaaaaa`, `ffffff`
  * there are examples under `test-in/`
* *outputColour0*&hellip;*outputColour3*: the output palette:
  * each colour is an NES colour index in hexadecimal (`00` to `3f`).
  * e.g. `0f 15 26 30`

The program writes `prg.bin` and `chr.bin`. (They will be overwritten if they already exist.)

## stillimage.asm
An NES program that displays the graphics data from `png2nesdata.py`. Needs the files `prg.bin` and `chr.bin`. Assembles with [ASM6](https://www.romhacking.net/utilities/674/)).

To assemble, run `asm6 stillimage.asm output.nes`

## Technical info on the NES program
* PRG ROM: 16 KiB (only 2 KiB is actually used)
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

