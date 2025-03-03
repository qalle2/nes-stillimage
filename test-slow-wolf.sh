rm -f test-out/*.nes

python3 png2nesdata.py test-in/wolf-32x25.png 0f 12 24 36
asm6 stillimage.asm   test-out/wolf-32x25.nes

rm prg.bin
rm chr.bin
