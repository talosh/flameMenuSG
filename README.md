# flameMenuSG
Interfaceless "menu-only" Shotgun integration for Autodesk Flame.
The goal is to create lightweight menu-driven integration that works 
out of the box for most common tasks.

#### THIS PROJECT IS CURRENTLY IN ALPHA STAGE
No releases has been made yet.
Lightweight publishing backend should be brought to basic functionality and all parts
combined in one singe file to become a first release.

NOTE: Refreshing custom menus in flame is currently limited to "refresh pyton hooks".
That means it is going to reload all pythong hooks currently enabled in the system 
and it may slow down your menu performance.

This code makes some assumptions local to the current configuration
I'm working with (most notably the storage roots are just hardcoded at the moment) 
so don't expect it is going to work on yours out of the box.

#### Make sure you set storage root to your projects root if you want to try it.

