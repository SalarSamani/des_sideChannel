#!/bin/bash
# Copy all files from ~/week2/task1 on hwsec-cw to the current local directory

echo "[INFO] Copying files from hwsec-cw:~/task1 to $(pwd)..."

scp -r hwsec-cw:~/week2/task1/* .

if [ $? -eq 0 ]; then
    echo "[INFO] ✅ Files successfully copied!"
else
    echo "[ERROR] ❌ Failed to copy files."
fi
