"""Ship the Chinese/English OCR models and settings with the desktop EXE."""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("rapidocr", includes=["*.yaml", "models/*.onnx"])
hiddenimports = ["onnxruntime"]
