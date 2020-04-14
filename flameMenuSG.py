import os
import sys
import sgtk
import time
import multiprocessing
import signal
import atexit

from pprint import pprint

bundle_name = 'flameMenuSG'
bundle_location = '/var/tmp'
menu_group_name = 'Menu(SG)'

DEBUG = True
        
# redirect termination signals to sys.exit()
# in order to avoid Flame crash window to come up
# when terminating child processes

def sigterm_handler(signum, frame):
    if DEBUG:
        print ('%s DEBUG\t: SIRTERM handler' % bundle_name)
    sys.exit()
signal.signal(signal.SIGINT, sigterm_handler)
signal.signal(signal.SIGTERM, sigterm_handler)


# flameAppFramework class takes care of preferences 
# and unpacking bundle to temporary location / cleanup on exit

class flameAppFramework(object):
    def __init__(self):
        self._bundle_name = bundle_name
        self._prefs = {}
        self._bundle_location = bundle_location
    
    @property
    def prefs(self):
        return self._prefs
    @prefs.setter
    def prefs(self, value):
        self._prefs = value
    
    @property
    def bundle_name(self):
        return self._bundle_name

    @property
    def bundle_location(self):
        return self._bundle_location

class flameApp(object):
    def __init__(self, framework):
        self._framework = framework
        self.menu_group_name = menu_group_name
        self.debug = DEBUG
        self.dynamic_menu_data = {}
        try:
            import flame
            self.flame = flame
        except:
            self.flame = None
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('calling %s' % name)
        return method

    def log(self, message):
        if self.debug:
            print ('%s DEBUG\t: %s' % (self._framework.bundle_name, message))

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')

    @property
    def framework(self):
        return self._framework

class flameShotgunApp(flameApp):
    def __init__(self, framework):
        flameApp.__init__(self, framework)
        self._sg_signout_marker = os.path.join(self.framework.bundle_location, self.framework.bundle_name + '.signout')
        self.sg_user = None
        self.sg_user_name = None
        self.sg_linked_project = ''
        self.TIMEOUT = 10

        if not os.path.isfile(self._sg_signout_marker):
            self.sg_user = self.get_user()
            if self.sg_user:
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

    def __del__(self):
        self.log('flameShotgunApp destructor')

    def get_user(self):        
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        try:
            user = authenticator.get_user()
        except sgtk.authentication.AuthenticationCancelled:
            return None

        # try to see if we're actually able to connect
        credentials_expired = False
        
        def credentials_handler(user, q):
            q.put(user.are_credentials_expired())
            return True
        
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=credentials_handler, args=(user, q))
        p.start()
        p.join(self.TIMEOUT)

        if p.is_alive():
            p.terminate()
            p.join()
            print ('timeout while trying to obtain Shotgun credentials')
            return None

        credentials_expired = q.get()

        if credentials_expired:
            authenticator.clear_default_user()
            user = authenticator.get_user()
        
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

class flameMenuProjectconnect(flameShotgunApp):
    def __getattr__(self, name):
        def method(*args, **kwargs):
            project = self.dynamic_menu_data.get(name)
            if project:
                self.link_project(project)
        return method
    
    def build_menu(self, hook_name):
        if not hook_name == 'get_main_menu_custom_ui_actions':
            return []
        if not self.flame:
            return []

        flame_project_name = self.flame.project.current_project.name
        self.sg_linked_project = self.flame.project.current_project.shotgun_project_name.get_value()

        menu = {'actions': []}

        if not self.sg_user:
            menu['name'] = self.menu_group_name

            menu_item = {}
            menu_item['name'] = 'Sign in to Shotgun'
            menu_item['execute'] = self.sign_in
            menu['actions'].append(menu_item)
        elif self.sg_linked_project:
            menu['name'] = self.menu_group_name

            menu_item = {}
            menu_item['name'] = 'Unlink `' + flame_project_name + '` from Shotgun project `' + self.sg_linked_project + '`'
            menu_item['execute'] = self.unlink_project
            menu['actions'].append(menu_item)
            menu_item = {}
            menu_item['name'] = 'Sign out ' + str(self.sg_user_name)
            menu_item['execute'] = self.sign_out
            menu['actions'].append(menu_item)
        else:
            menu['name'] = self.menu_group_name + ': Link `' + flame_project_name + '` to Shotgun'

            menu_item = {}
            menu_item['name'] = '~ Rescan Shotgun Projects'
            menu_item['execute'] = self.rescan
            menu['actions'].append(menu_item)

            menu_item = {}
            menu_item['name'] = '---'
            menu_item['execute'] = self.rescan
            menu['actions'].append(menu_item)

            projects = self.get_projects()
            projects_by_name = {}
            for project in projects:
                projects_by_name[project.get('name')] = project

            for project_name in sorted(projects_by_name.keys()):
                project = projects_by_name.get(project_name)
                self.dynamic_menu_data[str(id(project))] = project

                menu_item = {}
                menu_item['name'] = project_name
                menu_item['execute'] = getattr(self, str(id(project)))
                menu['actions'].append(menu_item)
            
            menu_item = {}
            menu_item['name'] = '--'
            menu_item['execute'] = self.rescan
            menu['actions'].append(menu_item)

            menu_item = {}
            menu_item['name'] = 'Sign out ' + str(self.sg_user_name)
            menu_item['execute'] = self.sign_out
            menu['actions'].append(menu_item)

        return menu

    def unlink_project(self, *args, **kwargs):
        self.flame.project.current_project.shotgun_project_name = ''
        self.sg_linked_project = ''
        self.rescan()

    def link_project(self, project):
        project_name = project.get('name')
        if project_name:
            self.flame.project.current_project.shotgun_project_name = project_name
        self.sg_linked_project = project_name
        self.rescan()

    def refresh(self, *args, **kwargs):        
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

    def rescan_flame_hooks(self, *args, **kwargs):
        self._framework.rescan()

print ('PYTHON\t: %s initializing' % bundle_name)
app_framework = flameAppFramework()
apps = []

def app_initialized(project_name):
    print ('===== app_initialized hook')
    print ('apps lenghth = %s' % len(apps))
    for n in range (0, len(apps)):
        print ('n = %s' % n)
        app = apps.pop(n)
        print (type(app))
        del app
    
    apps.append(flameMenuProjectconnect(app_framework))

    print (apps)

def get_main_menu_custom_ui_actions():
    menu = []
    for app in apps:
        menu.append(app.build_menu('get_main_menu_custom_ui_actions'))
        app.refresh()
    return menu