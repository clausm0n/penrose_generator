#!/bin/bash

# Log file
LOGFILE=/home/modus/startup.log

# Function to log messages
log_message() {
    echo "$(date): $1" >> $LOGFILE 2>&1
}

# Start logging
log_message "Starting startup script"

# Set the DISPLAY variable
export DISPLAY=:0
log_message "DISPLAY set to $DISPLAY"

# Set the XAUTHORITY variable
export XAUTHORITY=/home/modus/.Xauthority
log_message "XAUTHORITY set to $XAUTHORITY"

# Set the XDG_RUNTIME_DIR variable to the user's runtime directory
export XDG_RUNTIME_DIR=/run/user/$(id -u)
log_message "XDG_RUNTIME_DIR set to $XDG_RUNTIME_DIR"

# Log the environment for debugging
log_message "Environment variables:"
env >> $LOGFILE 2>&1

# Wait for X server to start by checking xset q directly
log_message "Waiting for X server to start"
counter=0
while ! xset q &>/dev/null; do
    sleep 1
    counter=$((counter + 1))
    log_message "Waited $counter seconds for X server"
    if [ $counter -gt 60 ]; then
        log_message "X server did not start within 60 seconds, exiting"
        exit 1
    fi
done

# Run the compiled executable and capture any errors
log_message "Running compiled executable"
/home/modus/penrose_generator/dist/penrose_generator >> $LOGFILE 2>&1
EXEC_STATUS=$?

# Capture the exit status of the executable
log_message "Executable exited with status $EXEC_STATUS"

if [ $EXEC_STATUS -ne 0 ]; then
    log_message "Executable failed, exiting startup script"
    exit 1
fi

# Disable screen timeout
log_message "Disabling screen timeout"
xset s off >> $LOGFILE 2>&1
xset -dpms >> $LOGFILE 2>&1
xset s noblank >> $LOGFILE 2>&1

log_message "Startup script completed"
