# flameMenuSG
Minimalistic context-menu driven Shotgun integration for Autodesk Flame.
It can be used stanalone without any special setup as well as alongside with Shotgun Pipeline Toolkit.

### INSTALLATION
copy flameMenuSG.py into /opt/Autodesk/shared/python 
(for user-only installation use /opt/Autodesk/user/{FlameUserName}/python)

### GETTING STARTED
https://vimeo.com/452727908

### CONFIGURATION
### Shotgun's "Local File Storage"
flameMenuPublisher needs at least one "Local File Storage" to be defined. This should be done on Shotgun website.
"Local File Stoarge" acts as a common place where you keep your projects. It is possible to create (and then delete)
as many "Local File Stoarage" records as needed in case projects are be stored in different locations.
The file storage to use with a particular flame project can be selected via flameMenuSG preferences dialog.

### Preferences Location
Preferences for flameMenuSG are stored next to Shotgun preferences, \~/Library/Caches/Shotgun/flameMenuSG/<hostname> on MacOSX and \~/.shotgun/flameMenuSG/<hostname> on 
Linux. flameMenuSG.prefs file contains global scope preferences, while flameMenuSG.<flame_user>.prefs and flameMenuSG.<flame_user>.<flame_project>.prefs are user scope and project scope preferences.

### Known issues
* In Media Panel max menu items is 160 ( at least on 2020.2 )