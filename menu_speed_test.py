import os
import sys
import sgtk
import time
import threading
import signal
import atexit
import base64
import uuid
import inspect
import pickle
from datetime import datetime
from pprint import pprint
from pprint import pformat
from sgtk.platform.qt import QtGui

bundle_name = 'flameMenuSG'
bundle_location = '/var/tmp'
menu_group_name = 'Menu(SG)'
# flameBatchBlessing
flame_batch_root = bundle_location
flame_batch_folder = 'flame_batch_setups'
# flameMenuNewbatch
steps_to_ignore = [
            'turnover',
            'roto'
    ]
types_to_include = [
            'Image Sequence',
            'Flame Render'
    ]
# flameMenuBatchLoader
storage_root = '/Volumes/projects'
DEBUG = True
        
# redirect termination signals to sys.exit()
# in order to avoid Flame crash window to come up
# when terminating child processes

def sigterm_handler(signum, frame):
    if DEBUG:
        print ('PYTHON\t: %s DEBUG\t: SIRTERM handler' % bundle_name)
    sys.exit()
signal.signal(signal.SIGINT, sigterm_handler)
signal.signal(signal.SIGTERM, sigterm_handler)


# flameAppFramework class takes care of preferences 
# and unpacking bundle to temporary location / cleanup on exit

class flameAppFramework(object):
    def __init__(self):
        self.name = self.__class__.__name__
        self._bundle_name = bundle_name
        self._prefs = {}
        self._bundle_location = bundle_location
        self.debug = DEBUG
        self.prefs_file_location = bundle_location + os.path.sep + bundle_name + '.prefs'
        self.log('[%s] waking up' % self.__class__.__name__)
        self.load_prefs()

    def log(self, message):
        if self.debug:
            print ('[DEBUG %s] %s' % (self._bundle_name, message))

    def load_prefs(self):
        try:
            prefs_file = open(self.prefs_file_location, 'r')
            self._prefs = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % self.prefs_file_location)
            self.log('preferences contents:\n' + pformat(self._prefs))
            return True
        except:
            self.log('unable to load preferences from %s' % self.prefs_file_location)
            return False

    def save_prefs(self):
        try:
            prefs_file = open(self.prefs_file_location, 'w')
            pickle.dump(self._prefs, prefs_file)
            prefs_file.close()
            self.log('preferences saved to %s' % self.prefs_file_location)
            self.log('preferences contents:\n' + pformat(self._prefs))
            return True
        except:
            self.log('unable to save preferences to %s' % self.prefs_file_location)
            return False

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

class flameMenuApp(object):
    def __init__(self, framework):
        self.name = self.__class__.__name__
        self.framework = framework
        self.menu_group_name = menu_group_name
        self.debug = DEBUG
        self.dynamic_menu_data = {}
        try:
            import flame
            self.flame = flame
        except:
            self.flame = None

        if not self.framework.prefs[self.name]:
            self.prefs = {}
            self.framework.prefs[self.name] = self.prefs
        else:
            self.prefs = self.framework.prefs[self.name]
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('calling %s' % name)
        return method

    def log(self, message):
        self.framework.log('[' + self.name + '] ' + message)

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log('Rescan Python Hooks')

class flameShotgunConnector(object):
    def __init__(self, framework):
        self.name = self.__class__.__name__
        self.framework = framework
        self.log('waking up')
        
        self.prefs = self.framework.prefs.get(self.name, None)
        if not self.prefs:
            self.prefs = {}
            self.prefs['user signed out'] = False
            self.framework.prefs[self.name] = self.prefs
        
        self.sg_user = None
        self.sg_human_user = None
        self.sg_user_name = None
        if not self.prefs.get('user signed out', False):
            self.log('requesting for Shotgun user')
            self.get_user()
        
        self.flame_project = None
        self.sg_linked_project = None
        self.sg_linked_project_id = None
        self.sg_state = {}
        self.sg_state['active projects'] = None
        self.sg_state['tasks'] = None
        # if not self.sg_user:
        #    self.sg_state['active projects'] = None
        # else:
        #    self.update_active_projects()
        self.sg_state_hash = hash(pformat(self.sg_state))

        self.loops = []
        self.threads = True
        self.loops.append(threading.Thread(target=self.state_scanner_loop, args=(1, )))
        self.loops.append(threading.Thread(target=self.active_projects_loop, args=(30   , )))
        self.loops.append(threading.Thread(target=self.update_tasks_loop, args=(30   , )))

        for loop in self.loops:
            loop.daemon = True
            loop.start()
        
        self.rescan_flag = False

    def __del__(self):
        self.log('destructor')

    def log(self, message):
        self.framework.log('[' + self.name + '] ' + message)

    def terminate_loops(self):
        self.threads = False
        for loop in self.loops:
            loop.join()

    def loop_timeout(self, timeout, start):
        time_passed = int(time.time() - start)
        if timeout <= time_passed:
            return
        else:
            for n in range((timeout - time_passed) * 10):
                if not self.threads:
                    self.log('leaving loop thread: %s' % inspect.currentframe().f_back.f_code.co_name)
                    break
                time.sleep(0.1)

    def state_scanner_loop(self, timeout):
        while self.threads:
            start = time.time()
            self.check_sg_linked_project()
            self.check_sg_state_hash()
            self.loop_timeout(timeout, start)
    
    def active_projects_loop(self, timeout):
        while self.threads:
            start = time.time()
            if not self.sg_user:
                self.log('no shotgun user, wanking...')
                self.loop_timeout(timeout, start)
            else:
                self.update_active_projects()
                self.log('found %s active projects' % len(self.sg_state.get('active projects', [])))
                self.loop_timeout(timeout, start)

    def update_tasks_loop(self, timeout):
        while self.threads:
            start = time.time()
            if not self.sg_user:
                self.loop_timeout(timeout, start)
            else:
                self.update_tasks()
                self.loop_timeout(timeout, start)

    def update_active_projects(self):
        if not self.sg_user:
            return False
        try:
            start = time.time()
            sg = self.sg_user.create_sg_connection()
            self.sg_state['active projects'] = sg.find(
                'Project',
                [['archived', 'is', False]],
                ['name', 'tank_name']
            )
            for project in self.sg_state.get('active projects', []):
                if project.get('name'):
                    if project.get('name') == self.sg_linked_project:
                        if 'id' in project.keys():
                            self.sg_linked_project_id = project.get('id')
                            self.sg_state['current project name'] = self.sg_linked_project
                            self.sg_state['current project id'] = self.sg_linked_project_id
                            self.log('project name: %s, id: %s' % (project.get('name'), project.get('id')))
            self.log('active projects update took %s' % (time.time() - start))
            return True
        except:
            return False

    def update_tasks(self):
        if not self.sg_user:
            return False
        if not self.sg_linked_project_id:
            return False
        try:
            start = time.time()
            sg = self.sg_user.create_sg_connection()
            task_filters = [['project.Project.id', 'is', self.sg_linked_project_id]]
            self.sg_state['tasks'] = sg.find('Task',
                task_filters,
                ['entity', 'task_assignees']
            )
            self.log('tasks update took %s' % (time.time() - start))
            return True
        except:
            return False

    def update_human_user(self):
        if not self.sg_user:
            return False
        try:
            start = time.time()
            sg = self.sg_user.create_sg_connection()
            self.sg_human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.sg_user.login]],
                ['name']
            )
            self.sg_user_name = self.sg_human_user.get('name', None)
            if not self.sg_user_name:
                self.sg_user_name = self.sg_user.login
            self.log('human user update took %s' % (time.time() - start))
            return True
        except:
            return False

    def get_user(self, *args, **kwargs):        
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        try:
            self.sg_user = authenticator.get_user()
        except sgtk.authentication.AuthenticationCancelled:
            self.prefs['user signed out'] = True
            return None

        if self.sg_user.are_credentials_expired():
            authenticator.clear_default_user()
            self.sg_user = authenticator.get_user()
        
        self.prefs['user signed out'] = False
        self.update_human_user()
        self.update_active_projects()

        return self.sg_user

    def clear_user(self, *args, **kwargs):
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        authenticator.clear_default_user()
        self.sg_user = None
        self.sg_human_user = None
        self.sg_user_name = None
        self.sg_state['active projects'] = None

    def check_sg_linked_project(self, *args, **kwargs):
        try:
            import flame
            if self.flame_project != flame.project.current_project.name:
                self.log('updating flame project name: %s' % flame.project.current_project.name)
                self.flame_project = flame.project.current_project.name
            if self.sg_linked_project != flame.project.current_project.shotgun_project_name:
                self.log('updating shotgun linked project name: %s' % flame.project.current_project.shotgun_project_name)
                self.sg_linked_project = flame.project.current_project.shotgun_project_name
                self.update_active_projects()
                self.log('updated active projects')
                # self.update_tasks()
        except:
            self.log('no flame module avaliable to import')

    def check_sg_state_hash(self, *args, **kwargs):
        state_hash = ''
        try:
            state_hash = hash(pformat(self.sg_state))
        except:
            return
        if self.sg_state_hash != state_hash:
            self.log('updating shotgun state hash')
            self.sg_state_hash = state_hash
            self.log('shotgun state hash updated')
            # flame seem to crash if "Rescan Python Hooks"
            # is not called from the main thread
            # so have to work over it with some sort of
            # rescan flag in connector
            self.rescan_flag = True 
            
            # try:
            #    import flame
            #    flame.execute_shortcut('Rescan Python Hooks')
            # except:
            #    self.log('check_sg_state_hash: no flame module to import yet')

class flameMenuNewBatch(flameMenuApp):
    def __init__(self):
        pass
        # flameMenuApp.__init__(self, framework)
        # self.connector = connector

        #if not self.prefs:
        #    self.prefs['show_all'] = False
        #    self.prefs['current_page'] = 0
        #    self.prefs['menu_max_items_per_page'] = 128

    def __getattr__(self, name):
        def method(*args, **kwargs):
            pass
            #entity = self.dynamic_menu_data.get(name)
            #if entity:
            #    self.create_new_batch(entity)
        return method

    def build_menu(self):
        number_of_menu_itmes = 256
        menu = {'name': 'test_speed_menu', 'actions': []}
        for i in xrange(1, number_of_menu_itmes+1):
            menu['actions'].append({
                'name': 'Test selection ' + str(i),
                # 'isVisible': self.scope_reel,
                'execute': getattr(self, 'menu_item_' + str(i))
            })
        return menu

def load_apps(apps):
    #apps.append(flameMenuProjectconnect(app_framework, shotgunConnector))
    #apps.append(flameBatchBlessing(app_framework))
    apps.append(flameMenuNewBatch())
    # apps.append(flameMenuBatchLoader(app_framework))
    if DEBUG:
        print ('[DEBUG %s] loaded %s' % (bundle_name, pformat(apps)))

print ('PYTHON\t: %s initializing' % bundle_name)
app_framework = flameAppFramework()
shotgunConnector = flameShotgunConnector(app_framework)
apps = []
load_apps(apps)

# --- FLAME HOOKS ---
def get_media_panel_custom_ui_actions():
    start = time.time()
    menu = {}
    for app in apps:
        if app.__class__.__name__ == 'flameMenuNewBatch':
            menu = app.build_menu()
    print('get_media_panel_custom_ui_actions menu update took %s' % (time.time() - start))
    return [menu]