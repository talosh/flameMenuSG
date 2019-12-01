# flameMenuSG
Interfaceless "menu-only" Shotgun integration for Autodesk Flame.
The goal is to create lightweight menu-driven integration that works 
out of the box for most common tasks.

### THIS PROJECT IS CURRENTLY IN ALPHA STAGE
No releases has been made yet.
Lighteight publishing backend should be brought to basic functionality and all parts
combined in one singe file to become a first release.
The current plan is to complete it before Dec 13 2019.

NOTE: Refreshing custom menus in flame is currently limited to "refresh pyton hooks".
This mean it is going to reload all pythong hooks currently enabled and it may slow down
your menu performance.

This code makes some assumptions local to the current configuration
I'm working with (most notably the storage roots are just hardcoded at the moment) 
so don't expect it is going to work on yours out of the box.
Is is engine-less from shotgun tookit point of view and is not registered as a shotgun app
but rather calls to shotgun directly. This is due to the limitations of the current flame engine 
in terms of manipulating flame menus dynamically.
