rm -f test-out/*.nes

python3 png2nesdata.py test-in/doom.png 0f 15 26 30
asm6 stillimage.asm test-out/doom.nes

python3 png2nesdata.py test-in/lena.png 0f 16 26 30
asm6 stillimage.asm test-out/lena.nes

python3 png2nesdata.py test-in/market.png 0f 17 27 30
asm6 stillimage.asm test-out/market.nes

python3 png2nesdata.py test-in/pattern.png 0f 00 00 30
asm6 stillimage.asm test-out/pattern.nes

python3 png2nesdata.py test-in/sonic.png 0f 12 27 30
asm6 stillimage.asm test-out/sonic.nes

rm prg.bin
rm chr.bin
