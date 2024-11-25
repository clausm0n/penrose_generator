#!/bin/bash

LOGFILE=/home/modus/startup.log
VENV_PATH=/home/modus/penrose_generator/.venv

log_message() {
    echo "$(date): $1" >> $LOGFILE 2>&1
}

log_message "Starting startup script"

export DISPLAY=:0
export XAUTHORITY=/home/modus/.Xauthority
export XDG_RUNTIME_DIR=/run/user/$(id -u)

cd /home/modus/penrose_generator
$VENV_PATH/bin/python penrose_generator.py --fullscreen -bt >> $LOGFILE 2>&1
EXEC_STATUS=$?

log_message "Generator exited with status $EXEC_STATUS"

if [ $EXEC_STATUS -ne 0 ]; then
    log_message "Generator failed, exiting startup script"
    exit 1
fi

xset s off >> $LOGFILE 2>&1
xset -dpms >> $LOGFILE 2>&1
xset s noblank >> $LOGFILE 2>&1

log_message "Startup script completed"