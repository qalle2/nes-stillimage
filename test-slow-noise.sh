rm -f test-out/*.nes

python3 png2nesdata.py test-in/noise-32x28.png
asm6 stillimage.asm   test-out/noise-32x28.nes

rm prg.bin
rm chr.bin
