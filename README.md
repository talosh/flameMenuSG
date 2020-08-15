# flameMenuSG
Interfaceless "menu-only" Shotgun integration for Autodesk Flame.
The goal is to create lightweight menu-driven integration that works 
out of the box for most common tasks.

### INSTALLATION
copy flameMenuSG.py into /opt/Autodesk/shared/python 
(for user-only installation use /opt/Autodesk/user/{FlameUserName}/python)

### CONFIGURATION
### Shotgun's "Local File Storage"
flameMenuPublisher needs at least one "Local File Storage" to be defined. This should be done on Shotgun website.
"Local File Stoarge" acts as a common place where you keep your projects. It is possible to create (and then delete)
as many "Local File Stoarage" records as needed if for a reason projects should be stored in different locations.
The file storage to use with a particular flame project can be selected via flameMenuSG preferences dialog.

Some things are still hardcoded so it might not work for you out of the box. If this is the case please let me know what exactly does not work for you.

NOTE: Refreshing custom menus in flame is currently limited to "refresh pyton hooks".
That means it is going to reload all pythong hooks currently enabled in the system.