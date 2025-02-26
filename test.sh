rm -f test-out/*.nes

rm -f chr.bin
python3 png2chr.py test-in/doom.png chr.bin
echo "hex 0f 15 26 30" > palette.asm
asm6 stillimage.asm test-out/doom.nes

rm -f chr.bin
python3 png2chr.py test-in/lena.png chr.bin
echo "hex 0f 16 26 30" > palette.asm
asm6 stillimage.asm test-out/lena.nes

rm -f chr.bin
python3 png2chr.py test-in/pattern.png chr.bin
echo "hex 0f 00 00 30" > palette.asm
asm6 stillimage.asm test-out/pattern.nes

rm -f chr.bin
python3 png2chr.py test-in/sonic.png chr.bin
echo "hex 0f 12 27 30" > palette.asm
asm6 stillimage.asm test-out/sonic.nes

rm chr.bin
rm palette.asm
