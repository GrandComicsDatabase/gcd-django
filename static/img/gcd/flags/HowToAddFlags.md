# How to add missing flag icons

Most of the PNG files in this directory were generated from the SVG files in
the `svg` directory, which originate from Wikipedia. These all are under some
open license and therefore reusable. For details, see the information at the
corresponding commons.wikipedia.org page about the flag as listed in
`svg/svg_sources`.

To add a missing icon:

* put the flag from commons.wikipedia.org in SVG format and rename it to `svg/<country-code>.svg`
* run `svg/convertScript` (which requires the `convert` command from ImageMagick)
* copy `<country-code>.png` to this directory
* add the source page in `svg/svg_sources`
* commit both the PNG and SVG file to git

Users in the "admin" group can check for missing flags using
http://www.comics.org/countries/

