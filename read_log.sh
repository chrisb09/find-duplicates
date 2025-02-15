#!/bin/sh

# screen -L find_duplicates.py ....

grep -B1 -A3 'Dry-run\|If you are happy\|In total' screenlog.0
