# mini tester wrapper. run this!

from scanner import *

print "Testing USB barcode scanner LS2208. Make sure you have one plugged in"

scanners = get_scanners()
scanner = None

if (scanners):
   print "Found a scanner!"
   print scanners
   scanner = scanners[0]

   print "------------------"
   print scanner.getBarcode()
