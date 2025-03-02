# nes-stillimage

Table of contents:
* [Introduction](#introduction)
* [png2nesdata.py](#png2nesdatapy)
* [png2nesdata2.py](#png2nesdata2py)
* [stillimage.asm](#stillimageasm)
* [Technical info on the NES program](#technical-info-on-the-nes-program)
* [Sources of images](#sources-of-images)

## Introduction
Three programs that let you convert an image (e.g. PNG) into an NES ROM that shows the image.

Examples of `png2nesdata.py` (screenshots from FCEUX):

![shareware DOS Doom title screen, 26&times;14 tiles](snap-doom-26x14.png)
![shareware DOS Doom title screen, 24&times;16 tiles](snap-doom-24x16.png)
![shareware DOS Doom title screen, 20&times;18 tiles](snap-doom-20x18.png)
![shareware DOS Doom title screen, 18&times;20 tiles](snap-doom-18x20.png)
![shareware DOS Doom title screen, 16&times;24 tiles](snap-doom-16x24.png)
![shareware DOS Doom title screen, 14&times;26 tiles](snap-doom-14x26.png)

## png2nesdata.py
A Python program that converts an image (e.g. PNG) into NES graphics data. Requires the [Pillow](https://python-pillow.org) module.

Command line arguments: *inputFile outputColour0 outputColour1 outputColour2 outputColour3*
* *inputFile*: the image file to read:
  * size (width&times;height) must be one of these:
    * 208&times;112 pixels (26&times;14 NES tiles, 13&times;7 attribute blocks)
    * 192&times;128 pixels (24&times;16 NES tiles, 12&times;8 attribute blocks)
    * 160&times;144 pixels (20&times;18 NES tiles, 10&times;9 attribute blocks)
    * 144&times;160 pixels (18&times;20 NES tiles, 9&times;10 attribute blocks)
    * 128&times;192 pixels (16&times;24 NES tiles, 8&times;12 attribute blocks)
    * 112&times;208 pixels (14&times;26 NES tiles, 7&times;13 attribute blocks)
  * may only contain these colours (hexadecimal RRGGBB): `000000`, `555555`, `aaaaaa`, `ffffff`
* *outputColour0*&hellip;*outputColour3*: the output palette:
  * each colour is an NES colour index in hexadecimal (`00` to `3f`).
  * optional; the default is `0f 00 10 30` (greyscale)

The program writes `prg.bin` and `chr.bin`. (They will be overwritten if they already exist.)

## png2nesdata2.py
Another Python program that converts an image (e.g. PNG) into NES graphics data. Allows for larger images than `png2nesdata.py` but will fail if they're too complex (too many distinct tiles). Requires the [Pillow](https://python-pillow.org) module.

Command line arguments: *inputFile outputColour0 outputColour1 outputColour2 outputColour3*
* *inputFile*: the image file to read:
  * the size (width&times;height) must be 256&times;224 pixels (32&times;28 NES tiles, 16&times;14 attribute blocks)
  * may only contain these colours (hexadecimal RRGGBB): `000000`, `555555`, `aaaaaa`, `ffffff`
  * if the image is too complex (has too many distinct tiles), it will be automatically simplified, which reduces the quality and takes a lot of time
* *outputColour0*&hellip;*outputColour3*: the output palette:
  * each colour is an NES colour index in hexadecimal (`00` to `3f`).
  * optional; the default is `0f 00 10 30` (greyscale)

The program writes `prg.bin` and `chr.bin`. (They will be overwritten if they already exist.)

## stillimage.asm
An NES program that displays the graphics data from `png2nesdata.py` or `png2nesdata2.py`. Needs the files `prg.bin` and `chr.bin`. Assembles with [ASM6](https://www.romhacking.net/utilities/674/)).

To assemble, run `asm6 stillimage.asm output.nes`

## Technical info on the NES program
* PRG ROM: 16 KiB (only 2 KiB is actually used)
* CHR ROM: 8 KiB
* mapper: NROM (iNES mapper number 0)
* name table mirroring: vertical
* no raster effects
* sprite size: 8&times;16 pixels
* this data is copied from files `prg.bin` and `chr.bin` (the files must be generated beforehand by `png2nesdata.py` or `png2nesdata2.py`):
  * name table
  * attribute table
  * sprites
  * palette
  * horizontal scroll value
  * vertical scroll value

## Sources of images
* `doom`: shareware version of *Doom* by id Software
* `lena`: [Ethically sourced Lena picture](https://mortenhannemose.github.io/lena/) by Morten Hannemose
* `wolf`: shareware version of *Wolfenstein 3D* by id Software
