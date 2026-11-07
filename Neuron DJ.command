#!/bin/zsh
cd -- "${0:A:h}" || exit 1
python3 scripts/start.py --open --load-model "$@"
