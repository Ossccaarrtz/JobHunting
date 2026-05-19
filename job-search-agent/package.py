"""
Empaqueta el Lambda para AWS: instala dependencias Linux + crea el zip.
Uso: python package.py
"""
import os
import shutil
import subprocess
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(SCRIPT_DIR, ".lambda-pkg")
ZIP_PATH = os.path.join(SCRIPT_DIR, "function.zip")
SOURCE_FILES = ["handler.py", "searcher.py", "filter.py", "storage.py", "notifier.py", "profile.json"]

# 1. Limpiar directorio anterior
print("Limpiando directorio anterior...")
shutil.rmtree(PKG_DIR, ignore_errors=True)
os.makedirs(PKG_DIR)

# 2. Instalar dependencias para Linux x86_64 (Lambda runtime)
print("Instalando dependencias (Linux manylinux)...")
result = subprocess.run([
    sys.executable, "-m", "pip", "install",
    "-r", os.path.join(SCRIPT_DIR, "requirements.txt"),
    "--target", PKG_DIR,
    "--platform", "manylinux2014_x86_64",
    "--python-version", "3.12",
    "--implementation", "cp",
    "--abi", "cp312",
    "--only-binary=:all:",
    "--no-cache-dir",
], check=True)

# 3. Copiar código fuente
print("Copiando código fuente...")
for f in SOURCE_FILES:
    shutil.copy(os.path.join(SCRIPT_DIR, f), PKG_DIR)

# 4. Crear zip
print("Creando zip...")
if os.path.exists(ZIP_PATH):
    os.remove(ZIP_PATH)

file_count = 0
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(PKG_DIR):
        # Excluir __pycache__ para reducir tamaño
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".pyc"):
                continue
            fp = os.path.join(root, file)
            arcname = os.path.relpath(fp, PKG_DIR)
            zf.write(fp, arcname)
            file_count += 1

size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
print(f"Zip creado: {size_mb:.1f}MB ({file_count} archivos)")
print(f"Path: {ZIP_PATH}")
