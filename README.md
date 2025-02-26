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

![shareware DOS Doom title screen, 24*16 tiles](snap-doom-24x16.png)
![shareware DOS Doom title screen, 16*24 tiles](snap-doom-16x24.png)
![ethically sourced Lena photo, 24*16 tiles](snap-lena-24x16.png)
![ethically sourced Lena photo, 16*24 tiles](snap-lena-16x24.png)

## png2nesdata.py
A Python program that converts an image (e.g. PNG) into NES graphics data. Requires the [Pillow](https://python-pillow.org) module.

Command line arguments: *inputFile outputColour0 outputColour1 outputColour2 outputColour3*
* *inputFile*: the image file to read:
  * size (width&times;height): one of these:
    * 192&times;128 pixels (24&times;16 NES tiles)
    * 128&times;192 pixels (16&times;24 NES tiles)
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
* sprite size: 8&times;16 pixels
* data copied from files generated by `png2nesdata.py`:
  * name table
  * attribute table
  * sprites
  * palette
  * horizontal scroll value
  * verticall scroll value

## Sources of images
* `doom.png`: shareware version of *Doom* by id Software
* `lena.png`: [Ethically sourced Lena picture](https://mortenhannemose.github.io/lena/) by Morten Hannemose

