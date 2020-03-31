from threading import Thread
import atexit

import os
import sys
import sgtk
import time

from pprint import pprint

menu_group_name = 'Menu(SG)'
prefs_location = '/var/tmp'

class flameAppFramework(object):
    def __init__(self):
        self._name = 'flameMenuSG'
        self._prefs = {}
        self._bundle_location = prefs_location
        try:
            import flame
            self._flame = flame
        except:
            self._flame = None
    
    def rescan(self):
        if not self.flame:
            try:
                import flame
                self._flame = flame
            except:
                self._flame = None
                
        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')

    @property
    def prefs(self):
        return self._prefs
    @prefs.setter
    def prefs(self, value):
        self._prefs = value
    
    @property
    def flame(self):
        return self._flame
    @flame.setter
    def flame(self, value):
        self._flame = value

    @property
    def name(self):
        return self._name

    @property
    def bundle_location(self):
        return self._bundle_location


class flameApp(object):
    def __init__(self, framework):
        self._framework = framework
        self.flame = fw.flame
        self.menu_group_name = menu_group_name
        self.dynamic_menu_data = {}
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('calling %s' % name)
        return method

    def rescan(self, *args, **kwargs):
        self._framework.rescan()

    @property
    def framework(self):
        return self._framework


class flameShotgunApp(flameApp):
    def __init__(self, framework):
        flameApp.__init__(self, framework)
        self._sg_signout_marker = os.path.join(self.framework.bundle_location, self.framework.name + '.signout')
        self.sg_user = None
        self.sg_user_name = None
        self.sg_linked_project = ''

        if not os.path.isfile(self._sg_signout_marker):
            self.sg_user = self.get_user()
            sg = self.sg_user.create_sg_connection()
            human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.sg_user.login]],
                ['name']
            )
            self.sg_user_name = human_user.get('name', None)
            if not self.sg_user_name:
                self.sg_user_name = self.sg_user.login

        if self.flame:
            self.sg_linked_project = self.flame.project.current_project.shotgun_project_name.get_value()

    def get_user(self):        
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        try:
            user = authenticator.get_user()
            if user.are_credentials_expired():
                authenticator.clear_default_user()
                user = authenticator.get_user()
        except sgtk.authentication.AuthenticationCancelled:
            return None

        return user

    def clear_user(self):
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        authenticator.clear_default_user()

    def get_projects(self, *args, **kwargs):
        sg = self.sg_user.create_sg_connection()
        projects = sg.find(
            'Project',
            [['archived', 'is', False]],
            ['name', 'tank_name']
        )
        return projects

    def get_shotgun_project_id(self, shotgun_project_name):
        user = _get_user()
        sg = user.create_sg_connection()
        if not sg:
            return None

        proj = sg.find_one(
            'Project',
            [['name', 'is', shotgun_project_name]]
        )

        if proj :
            # Found project, return it.
            return proj['id']

    def sign_in(self, *args, **kwargs):
        if os.path.isfile(self._sg_signout_marker):
            os.remove(self._sg_signout_marker)
        self.sg_user = self.get_user()
        if not self.sg_user:
            self.sign_out()
        sg = self.sg_user.create_sg_connection()
        human_user = sg.find_one('HumanUser', 
            [['login', 'is', self.sg_user.login]],
            ['name']
        )
        self.sg_user_name = human_user.get('name', None)
        if not self.sg_user_name:
            self.sg_user_name = self.sg_user.login
        self.rescan()

    def sign_out(self, *args, **kwargs):
        self.clear_user()
        open(self._sg_signout_marker, 'a').close()
        self.sg_user = None
        self.sg_user_name = None
        self.rescan()


threads = []

def wait_for_threads_at_exit():
    global threads
    if len(threads) > 0:
        for thread in threads:
            print("Waiting for %s" % thread.name)
            # join() waits for the thread to finish before relinquishing
            # control, making sure everything is done before exit.
            thread.join()
    threads = []

# Clean up by Python on exit
atexit.register(wait_for_threads_at_exit)

# The actual code to execute in a thread.
def async_callback(param1, param2):
    print("async_callback(%s, %s)\n" % (str(param1), str(param2)))

def render_ended(moduleName, sequenceName, elapsedTimeInSeconds):
    #Creates the separate thread
    thread = Thread(
        target=async_callback,
        name="async callback",
        args=(moduleName, sequenceName, ))
    thread.start()

    # Add to threads[] the just created thread, to keep track and
    # clean up on exit.
    threads.append(thread)