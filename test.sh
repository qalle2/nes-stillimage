rm -f test-out/*.nes

echo "=== png2nesdata.py ==="
echo

python3 png2nesdata.py test-in/doom-26x14.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-26x14.nes

python3 png2nesdata.py test-in/doom-24x16.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-24x16.nes

python3 png2nesdata.py test-in/doom-20x18.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-20x18.nes

python3 png2nesdata.py test-in/doom-18x20.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-18x20.nes

python3 png2nesdata.py test-in/doom-16x24.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-16x24.nes

python3 png2nesdata.py test-in/doom-14x26.png 0f 15 26 30
asm6 stillimage.asm test-out/doom-14x26.nes

python3 png2nesdata.py test-in/extracolour-24x16.png
asm6 stillimage.asm test-out/extracolour-24x16.nes

python3 png2nesdata.py test-in/lena-24x16.png 0f 16 26 30
asm6 stillimage.asm test-out/lena-24x16.nes

python3 png2nesdata.py test-in/lena-16x24.png 0f 16 26 30
asm6 stillimage.asm test-out/lena-16x24.nes

echo
echo "=== png2nesdata2.py ==="
echo

python3 png2nesdata2.py test-in/repeating-32x28.png
asm6 stillimage.asm test-out/repeating-32x28.nes
echo

python3 png2nesdata2.py test-in/wolf-32x28-nodith-simple.png 0f 12 24 36
asm6 stillimage.asm test-out/wolf-32x28-nodith-simple.nes
echo

echo "This will fail:"
python3 png2nesdata2.py test-in/wolf-32x28-nodith.png
echo

rm prg.bin
rm chr.bin
