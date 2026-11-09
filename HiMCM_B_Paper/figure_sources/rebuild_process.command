#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/Library/TeX/texbin:$PATH"
mkdir -p ../build
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=../build 00_cooling_service_process.tex
cp ../build/00_cooling_service_process.pdf ../figures/00_cooling_service_process.pdf
print "Updated figures/00_cooling_service_process.pdf"
