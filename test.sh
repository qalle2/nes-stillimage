rm -f test-out/*.nes

python3 png2nesdata.py test-in/blank-32x28.png
asm6 stillimage.asm   test-out/blank-32x28.nes
echo

python3 png2nesdata.py test-in/extracolour-26x6.png
asm6 stillimage.asm   test-out/extracolour-26x6.nes
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

python3 png2nesdata.py test-in/repeating-32x28.png
asm6 stillimage.asm   test-out/repeating-32x28.nes
echo

rm -f prg.bin chr.bin

echo "test-out/:"
ls -1 test-out/
echo
