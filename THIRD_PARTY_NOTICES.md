# Third-party notices

The application's source code and packaged application are provided under GNU AGPL version 3; see `LICENSE.txt` for the full terms. This license does not replace the notices or license terms of the individual dependencies below.

This project uses PyMuPDF 1.28.2 (including MuPDF), distributed under the GNU Affero General Public License, version 3, or a commercial license from Artifex. The dependency's bundled COPYING file is reproduced at `licenses/PyMuPDF-COPYING.txt`.

Upstream project and source distributions: https://github.com/pymupdf/PyMuPDF and https://pypi.org/project/PyMuPDF/1.28.2/#files . MuPDF upstream source: https://mupdf.com/ . The corresponding release/source trees provide the third-party notices for components incorporated by these dependencies.

Packaged Windows binaries include the CPython runtime and Tcl/Tk. CPython's bundled license is reproduced at `licenses/Python-LICENSE.txt`; Tcl/Tk license notices supplied by the build runtime are included in that folder as available.

GUI file dropping uses tkinterdnd2 0.6.3, distributed under the MIT license (`licenses/tkinterdnd2-LICENSE.txt`), and its bundled TkDnD 2.10.2 extension (`licenses/TkDnD-license.terms`). Upstream sources and notices: https://github.com/Eliav2/tkinterdnd2 and https://github.com/petasis/tkdnd .

The executables are built with PyInstaller 6.22.3, licensed under GPL with a bootloader distribution exception. Its COPYING text is provided at `licenses/PyInstaller-COPYING.txt`. See https://pyinstaller.org/en/stable/license.html .

The complete Windows ZIP includes all application source files. The portable GUI ZIP uses the unchanged v1.4.1 application source, available at https://github.com/Zerozero05/PDF_Bookmarks/tree/v1.4.1 . Dependency sources and license terms are controlled by their respective upstream projects.

The v1.3 desktop application adds RapidOCR 3.9.2 (Apache 2.0) and its bundled PP-OCRv6 small detection/recognition and PP-OCRv4 mobile classification ONNX models, derived from PaddleOCR. Upstream projects and licenses: https://github.com/RapidAI/RapidOCR and https://github.com/PaddlePaddle/PaddleOCR . The upstream license texts are reproduced under `licenses/ocr/RapidOCR` and `licenses/ocr/PaddleOCR`.

Local CPU inference uses ONNX Runtime 1.22.1 (MIT), NumPy 2.2.6 (BSD), OpenCV-Python 4.11.0.86 (Apache 2.0 and bundled third-party terms), and their supporting dependencies. License and notice files distributed with the actual build environment are collected under `licenses/ocr`, including ONNX Runtime third-party notices, OpenCV third-party notices, NumPy notices, GEOS/Shapely notices, Pillow, PyClipper, OmegaConf, PyYAML and supporting Python dependencies. GitHub Actions builds the GUI and CLI separately from the maintained source; the CLI keeps its existing behavior and does not use the OCR modules.
