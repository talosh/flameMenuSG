# flameMenuSG
Context-menu driven Shotgun integration for Autodesk Flame.
It is lightweight single-file alternative to Shotgun Desktop / Pipeline Toolkit and allows a hassle-free integration out of the box.

### INSTALLATION
copy flameMenuSG.py into /opt/Autodesk/shared/python 
(for user-only installation use /opt/Autodesk/user/{FlameUserName}/python)

### GETTING STARTED
placeholder for a video link

### CONFIGURATION
### Shotgun's "Local File Storage"
flameMenuPublisher needs at least one "Local File Storage" to be defined. This should be done on Shotgun website.
"Local File Stoarge" acts as a common place where you keep your projects. It is possible to create (and then delete)
as many "Local File Stoarage" records as needed in case projects are be stored in different locations.
The file storage to use with a particular flame project can be selected via flameMenuSG preferences dialog.

### Preferences
Preferences for flameMenuSG are stored next to Shotgun preferences, 
on MacOSX it is \~/Library/Caches/Shotgun/flameMenuSG/<hostname> and on 
Linux \~/.shotgun/flameMenuSG/<hostname>. flameMenuSG.prefs file contains global scope preferences, while flameMenuSG.<flame_user>.prefs and flameMenuSG.<flame_user>.<flame_project>.prefs are user scope and project scope preferences.


Some things are still hardcoded so it might not work for you out of the box. If this is the case please let me know what exactly does not work for you.

NOTE: Refreshing custom menus in flame is currently limited to "refresh pyton hooks".
That means it is going to reload all pythong hooks currently enabled in the system.