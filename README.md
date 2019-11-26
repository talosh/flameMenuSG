# flameMenuSG
interfaceless "menu-only" Shotgun integration demo for Autodesk Flame.

This code makes some assumptions local to the current configuration
I'm working with (most notably the storage roots are just hardcoded at the moment) 
so don't expect it is going to work on yours out of the box. 
Is is engine-less from shotgun tookit point of view and is not registered as a shotgun app
but rather calls to shotgun directly. This is due to the limitations of the current flame engine 
in terms of manipulating flame menus dynamically.
