rm -f test-out/*.nes

python3 png2nesdata.py test-in/apogee-32x25.png
asm6 stillimage.asm   test-out/apogee-32x25.nes
echo

python3 png2nesdata.py test-in/blank.png
asm6 stillimage.asm   test-out/blank.nes
echo

python3 png2nesdata.py test-in/doom-32x24.png
asm6 stillimage.asm   test-out/doom-32x24.nes
echo

python3 png2nesdata.py test-in/extracolour.png
asm6 stillimage.asm   test-out/extracolour.nes
echo

python3 png2nesdata.py test-in/keen4-32x25.png
asm6 stillimage.asm   test-out/keen4-32x25.nes
echo

python3 png2nesdata.py test-in/lena-16x24.png
asm6 stillimage.asm   test-out/lena-16x24.nes
echo

python3 png2nesdata.py test-in/pattern-1x1.png
asm6 stillimage.asm   test-out/pattern-1x1.nes
echo

python3 png2nesdata.py test-in/pattern-29x28.png
asm6 stillimage.asm   test-out/pattern-29x28.nes
echo

python3 png2nesdata.py test-in/pattern-30x28.png
asm6 stillimage.asm   test-out/pattern-30x28.nes
echo

python3 png2nesdata.py test-in/pattern-31x28.png
asm6 stillimage.asm   test-out/pattern-31x28.nes
echo

python3 png2nesdata.py test-in/pattern-32x25.png
asm6 stillimage.asm   test-out/pattern-32x25.nes
echo

python3 png2nesdata.py test-in/pattern-32x26.png
asm6 stillimage.asm   test-out/pattern-32x26.nes
echo

python3 png2nesdata.py test-in/pattern-32x27.png
asm6 stillimage.asm   test-out/pattern-32x27.nes
echo

python3 png2nesdata.py test-in/pattern-32x28.png
asm6 stillimage.asm   test-out/pattern-32x28.nes
echo

python3 png2nesdata.py test-in/qalle-fursona.png
asm6 stillimage.asm   test-out/qalle-fursona.nes
echo

python3 png2nesdata.py test-in/spriteflip.png
asm6 stillimage.asm   test-out/spriteflip.nes
echo

python3 png2nesdata.py test-in/spriterepeat.png
asm6 stillimage.asm   test-out/spriterepeat.nes
echo

python3 png2nesdata.py test-in/wolf-32x25.png
asm6 stillimage.asm   test-out/wolf-32x25.nes
echo

rm -f prg.bin chr.bin

echo "test-out/:"
ls -1 test-out/
echo
