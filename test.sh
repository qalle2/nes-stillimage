rm -f test-out/*.nes

python3 png2nesdata.py test-in/doom-24x16.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-24x16.nes

python3 png2nesdata.py test-in/doom-16x24.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-16x24.nes

python3 png2nesdata.py test-in/lena-24x16.png 0f 16 26 30
asm6 stillimage.asm test-out/lena-24x16.nes

python3 png2nesdata.py test-in/lena-16x24.png 0f 16 26 30
asm6 stillimage.asm test-out/lena-16x24.nes

python3 png2nesdata.py test-in/market-24x16.png 0f 17 27 30
asm6 stillimage.asm test-out/market-24x16.nes

python3 png2nesdata.py test-in/pattern-24x16.png 0f 00 00 30
asm6 stillimage.asm test-out/pattern-24x16.nes

python3 png2nesdata.py test-in/pattern-16x24.png 0f 00 00 30
asm6 stillimage.asm test-out/pattern-16x24.nes

python3 png2nesdata.py test-in/sonic-24x16.png 0f 12 27 30
asm6 stillimage.asm test-out/sonic-24x16.nes

python3 png2nesdata.py test-in/tileindexes-16x24.png 0f 16 26 30
asm6 stillimage.asm test-out/tileindexes-16x24.nes

rm prg.bin
rm chr.bin
