# flameMenuSG
Interfaceless "menu-only" Shotgun integration for Autodesk Flame.
The goal is to create lightweight menu-driven integration that works 
out of the box for most common tasks.

### INSTALLATION
copy flameMenuSG.py into /opt/Autodesk/shared/python 
(for user-only install use /opt/Autodesk/user/{FlameUserName}/python)

### Shotgun's "Local File Storage"
| storage root | project name
/media/projects/myproject

### CONFIGURATION

Make sure to set default_storage_root on top of flameMenuSG.py file to your actual projects root if you want to try it out.
Some things are still hardcoded so it might not work for you out of the box. If this is the case please let me know what exactly does not work for you.

NOTE: Refreshing custom menus in flame is currently limited to "refresh pyton hooks".
That means it is going to reload all pythong hooks currently enabled in the system.