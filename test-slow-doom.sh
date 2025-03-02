rm -f test-out/*.nes

python3 png2nesdata.py test-in/doom-16x14.png 0f 16 26 30
asm6 stillimage.asm   test-out/doom-16x14.nes

rm prg.bin
rm chr.bin
