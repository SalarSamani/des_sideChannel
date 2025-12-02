#!/bin/bash
# Copy all files from ~/task5 on hwsec-cw to the current local directory

echo "[INFO] Copying files ..."

scp -r hwsec-cw:~/week1/task5/*.py .
scp -r hwsec-cw:~/week1/task5/*.txt .

if [ $? -eq 0 ]; then
    echo "[INFO] ✅ Files successfully copied!"
else
    echo "[ERROR] ❌ Failed to copy files."
fi
