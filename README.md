Raspberry Pi Display Configuration Guide
This guide provides detailed instructions on how to prevent your Raspberry Pi's display from turning off automatically, and how to configure the environment variable DISPLAY for running GUI applications correctly from the terminal.

Prevent Display from Turning Off
To keep the display active and prevent it from turning off, which is typically managed by the screen blanking feature in the LightDM display manager, follow these steps:

1. Edit LightDM Configuration
LightDM controls the login session and manages user authentication. To disable the screen blanking:

Open the Terminal: Access your terminal through your Raspberry Pi's desktop environment or via SSH.

Edit the LightDM Configuration File:

bash
Copy code
sudo nano /etc/lightdm/lightdm.conf
Modify or Add the [Seat:*] Section:
Within the lightdm.conf file, locate the [Seat:*] section or create it if it does not exist. Add the following line under this section:

ini
Copy code
xserver-command=X -s 0 dpms
This line instructs the X server to disable DPMS (Display Power Management Signaling) and screen saver features, preventing the display from turning off automatically.

Save and Exit: Press CTRL+X, then Y to save, and Enter to exit the nano editor.

2. Restart LightDM
Apply the changes by restarting LightDM:

bash
Copy code
sudo systemctl restart lightdm
This command will restart the display manager using the updated configuration, effectively disabling display power management.

Setting Up the DISPLAY Environment Variable
When running GUI applications from the terminal or scripts, especially when logged in via SSH or from a different user account, you need to ensure the DISPLAY environment variable is set correctly.

Export DISPLAY Variable
Open the Terminal.

Set the DISPLAY Variable Temporarily:
For the current session, you can set the DISPLAY variable by executing:

bash
Copy code
export DISPLAY=:0
This command sets the DISPLAY environment variable to :0, which is typically the default display for the Raspberry Pi when running a desktop environment.

Making Permanent Changes
For persistent changes across reboots and for all sessions:

Edit the Global Profile:

bash
Copy code
sudo nano /etc/profile
Add the Export Command:
At the end of the file, add:

bash
Copy code
export DISPLAY=:0
Save and Exit: Press CTRL+X, then Y to save, and Enter to exit.