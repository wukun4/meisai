#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/Library/TeX/texbin:$PATH"
mkdir -p build
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build HiMCM-MidMCM_Summary.tex
cp build/HiMCM-MidMCM_Summary.pdf HiMCM-MidMCM_Summary.pdf
print "Compiled: $PWD/HiMCM-MidMCM_Summary.pdf"
