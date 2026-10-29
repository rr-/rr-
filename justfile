# List recipes
default:
    @just --list

# Render the banner and the section headers into art/
art:
    cd tools && python3 banner.py && python3 gen.py

# Render the rotation into PNGs in build/banners/, one per theme
png:
    cd tools && python3 png.py

# Copy the rotation's PNGs into bad.pink, which serves a random one at
# bad.pink/github/banner-light.png and banner-dark.png
sync dest="../bad.pink/apps/main/github/banners": png
    mkdir -p {{dest}}
    rm -f {{dest}}/*.svg {{dest}}/*.png
    cp build/banners/*.png {{dest}}/

# Render the README with both themes into build/preview.html
preview:
    python3 tools/preview.py

# Serve the preview on localhost and rebuild it live as the README and art change
watch *args:
    python3 tools/preview.py --watch {{args}}

# Check the LZSS codec round-trips
test:
    python3 tools/lzss.py --test
