rm -f test-out/*.nes

# not supported yet
#rm -f prg.bin chr.bin
#python3 png2nesdata.py test-in/extracolour-12x8.png
#asm6 stillimage.asm   test-out/extracolour-12x8.png
#echo

# not supported yet
#rm -f prg.bin chr.bin
#python3 png2nesdata.py test-in/lena-8x12.png 0f 16 26 30
#asm6 stillimage.asm   test-out/lena-8x12.png
#echo

rm -f prg.bin chr.bin
python3 png2nesdata.py test-in/pattern-16x14.png
asm6 stillimage.asm   test-out/pattern-16x14.png
echo

rm -f prg.bin chr.bin
python3 png2nesdata.py test-in/repeating-16x14.png
asm6 stillimage.asm   test-out/repeating-16x14.png
echo

# not supported yet
#rm -f prg.bin chr.bin
#python3 png2nesdata.py test-in/tileindexes-8x12.png
#asm6 stillimage.asm   test-out/tileindexes-8x12.png
#echo

rm -f prg.bin chr.bin
