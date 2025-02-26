; Display a still image on the NES. Assembles with ASM6.
; - no raster effects
; - 4 colours
; - image itself:
;     - size: 192*128 px = 24*16 tiles
;     - location: tiles (4,8)-(27,23) and AT blocks (2,4)-(13,11)
; - left & center third of image:
;     - made of BG
;     - size: 16*16 tiles
;     - location: tiles (4,8)-(19,23) and AT blocks (2,4)-(9,11)
;     - BG subpalette 0
; - right third of image:
;     - made of 8*16-pixel sprites
;     - size: 8*16 tiles = 8*8 sprites
;     - location: tiles (20,8)-(27,23)
;     - sprite subpalette 0
;     - any BG tile
;     - BG subpalette 1
; - margins:
;     - any BG tile
;     - BG subpalette 1
; - palettes:
;     - BG0 = SPR0 = image colours
;     - BG1: filled with image colour #0

; --- Constants ---------------------------------------------------------------

; RAM
sprite_data     equ $0200  ; OAM page ($100 bytes)

; memory-mapped registers
ppu_ctrl        equ $2000
ppu_mask        equ $2001
ppu_status      equ $2002
oam_addr        equ $2003
ppu_scroll      equ $2005
ppu_addr        equ $2006
ppu_data        equ $2007
dmc_freq        equ $4010
oam_dma         equ $4014
snd_chn         equ $4015
joypad1         equ $4016
joypad2         equ $4017

; --- iNES header -------------------------------------------------------------

                ; see https://wiki.nesdev.org/w/index.php/INES
                base $0000
                db "NES", $1a            ; file id
                db 1, 1                  ; 16 KiB PRG ROM, 8 KiB CHR ROM
                db %00000001, %00000000  ; NROM mapper, vertical NT mirroring
                pad $0010, $00           ; unused

; --- image palette -----------------------------------------------------------

                base $c000              ; last 16 KiB of CPU address space
                pad $fe00, $ff          ; only use last 512 bytes

image_palette   ; a file that defines 4 bytes, e.g. "hex 0f 14 24 30";
                ; here for easy hex editing (if the need arises)
                include "palette.asm"
                pad $fe04, $00

; --- initialisation ----------------------------------------------------------

reset           ; initialise the NES
                ; see https://wiki.nesdev.org/w/index.php/Init_code
                sei                     ; ignore IRQs
                cld                     ; disable decimal mode
                ldx #%01000000
                stx joypad2             ; disable APU frame IRQ
                ldx #$ff
                txs                     ; initialize stack pointer
                inx
                stx ppu_ctrl            ; disable NMI
                stx ppu_mask            ; disable rendering
                stx dmc_freq            ; disable DMC IRQs
                stx snd_chn             ; disable sound channels

                jsr wait_vbl_start      ; wait until next VBlank starts
                jsr init_ram            ; initialise main RAM

                jsr wait_vbl_start      ; wait until next VBlank starts
                jsr init_ppu_mem        ; initialise PPU memory

                jsr wait_vbl_start      ; wait until next VBlank starts

                lda #0
                sta ppu_scroll
                lda #8                  ; center image vertically
                sta ppu_scroll
                ; enable NMI on VBlank; use 8*16-px sprites;
                ; use PT0 for BG; use PT1 for sprites
                lda #%10101000
                sta ppu_ctrl
                lda #%00011110 ; show background and sprites
                sta ppu_mask

main_loop       jmp main_loop           ; an infinite loop

; --- small subroutines -------------------------------------------------------

wait_vbl_start  bit ppu_status          ; wait until next VBlank starts
-               lda ppu_status
                bpl -
                rts

set_ppu_addr    sty ppu_addr            ; Y*$100+A -> address
                sta ppu_addr
                rts

; --- init_ram ----------------------------------------------------------------

init_ram        ; generate sprite data (8*8 sprites) in RAM
                ldx #0                  ; 0, 4, ..., 252
                ;
                ; Y position minus one (4*16-9 to 11*16-9)
sprite_loop     txa                     ; %AAABBB00
                lsr a
                and #%01110000          ; %0AAA0000
                clc
                adc #4*16-9
                sta sprite_data+0,x
                ;
                ; tile index (bits: %ABBCCC00 -> %0BBACCC1)
                txa                     ; %ABBCCC00
                asl a                   ; %BBCCC000
                rol a                   ; %BCCC000A
                rol a                   ; %CCC000AB
                rol a                   ; %CC000ABB
                and #%00000111          ; %00000ABB
                tay
                txa                     ; %ABBCCC00
                lsr a                   ; %0ABBCCC0
                and #%00001110          ; %0000CCC0
                ora tile_index_lut,y    ; %0BBACCC1
                sta sprite_data+1,x
                ;
                ; attributes
                lda #%00000000
                sta sprite_data+2,x
                ;
                ; X position (20*8...27*8)
                txa                     ; bits: IIIiii00
                asl a
                and #%00111000          ; bits: 00iii000
                clc
                adc #20*8
                sta sprite_data+3,x
                ;
                inx
                inx
                inx
                inx
                bne sprite_loop
                ;
                rts

tile_index_lut  ; a look-up table for sprite tile indexes;
                ; bits: %00000ABB -> %0BBA0001
                hex 01 21 41 61 11 31 51 71

; --- init_ppu_mem ------------------------------------------------------------

init_ppu_mem    ; initialise PPU memory

                ; set palette (while still in VBlank)
                ldy #$3f
                lda #$00
                jsr set_ppu_addr        ; Y*$100+A -> address
                ldy #2                  ; outer loop counter (BG/SPR)
                ;
palette_loop    ldx #0                  ; 1st subpal: image palette as-is
-               lda image_palette,x
                sta ppu_data
                inx
                cpx #4
                bne -
                ;
                lda image_palette+0     ; 2nd-4th subpal: fill with colour 0
                ldx #(3*4)
-               sta ppu_data
                dex
                bne -
                ;
                dey
                bne palette_loop

                ; this should avoid a glitch
                ldy #$3f
                lda #$00
                jsr set_ppu_addr        ; Y*$100+A -> address

                ; generate NT & AT data
                ;
                ; tiles (4,8)-(19,23): left & center third of image;
                ; all other tiles: $00 (any tile could be used)

                ldy #$20
                lda #$00
                jsr set_ppu_addr        ; Y*$100+A -> address

                lda #$00                ; NT top margin: 8*32 tiles
                ldx #0
-               sta ppu_data
                inx
                bne -

                ; NT rows with the image itself: 16*(4+16+12) tiles
                ldy #0                  ; 0...15
                ;
image_nt_loop   lda #$00                ; left margin
                ldx #4
-               sta ppu_data
                dex
                bne -
                ;
                ; left and middle third of image; tiles: (Y*16)...(Y*16+15)
                tya
                asl a
                asl a
                asl a
                asl a
                ldx #0
-               sta ppu_data
                clc
                adc #1
                inx
                cpx #16
                bne -
                ;
                ; right third of image and right margin
                lda #$00
                ldx #12
-               sta ppu_data
                dex
                bne -
                ;
                iny
                cpy #16
                bne image_nt_loop

                lda #$00                ; NT bottom margin: 6*32 tiles
                ldx #192
-               sta ppu_data
                dex
                bne -

                lda #%01010101          ; AT top margin: 2*8 bytes
                ldx #16
-               sta ppu_data
                dex
                bne -

                ; AT rows with the image itself: 4*(1+4+3) bytes
                ldy #4
                ;
image_at_loop   lda #%01010101          ; left margin
                sta ppu_data
                ;
                lda #%00000000          ; left and middle third of image
                ldx #4
-               sta ppu_data
                dex
                bne -
                ;
                lda #%01010101          ; right third of image and right margin
                ldx #3
-               sta ppu_data
                dex
                bne -
                ;
                dey
                bne image_at_loop

                lda #%01010101          ; AT bottom margin: 2*8 bytes
                ldx #16
-               sta ppu_data
                dex
                bne -

                rts

; --- interrupt routines ------------------------------------------------------

nmi             bit ppu_status
                lda #>sprite_data       ; do OAM DMA
                sta oam_dma
irq             rti                     ; IRQ unused

; --- interrupt vectors -------------------------------------------------------

                pad $fffa, $ff
                dw nmi, reset, irq      ; IRQ unused

; --- CHR ROM -----------------------------------------------------------------

                base $0000
                incbin "chr.bin"
                pad $1800, $ff          ; only 6 KiB actually used
                pad $2000, $ff
