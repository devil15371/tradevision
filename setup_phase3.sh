#!/bin/bash
# Phase 3 dependency setup script
# Run: nohup bash setup_phase3.sh &

set -e
LOG="/home/user1/export/tradevision/logs/setup_phase3.log"

echo "[$(date)] Starting Phase 3 setup..." | tee -a $LOG

source /home/user1/export/tradevision/venv/bin/activate

echo "[$(date)] Installing bitsandbytes..." | tee -a $LOG
pip install --no-deps bitsandbytes >> $LOG 2>&1

echo "[$(date)] Installing unsloth_zoo..." | tee -a $LOG
pip install --no-deps unsloth_zoo >> $LOG 2>&1

echo "[$(date)] Installing peft..." | tee -a $LOG
pip install --no-deps peft >> $LOG 2>&1

echo "[$(date)] Installing trl..." | tee -a $LOG
pip install --no-deps trl >> $LOG 2>&1

echo "[$(date)] Installing datasets..." | tee -a $LOG
pip install datasets >> $LOG 2>&1

echo "[$(date)] Verifying..." | tee -a $LOG
python3 -c "import unsloth; import trl; import peft; import bitsandbytes; print('ALL OK')" >> $LOG 2>&1

echo "[$(date)] DONE" | tee -a $LOG
