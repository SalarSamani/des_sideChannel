#!/bin/bash
# Copy all files from ~/task3 on hwsec-cw to the current local directory

echo "[INFO] Copying files ..."

scp -r hwsec-cw:~/week1/task3/* .

if [ $? -eq 0 ]; then
    echo "[INFO] ✅ Files successfully copied!"
else
    echo "[ERROR] ❌ Failed to copy files."
fi
