'''
flameMenuSG
Flame 2020 and higher
written by Andrii Toloshnyy
andriy.toloshnyy@gmail.com
'''

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
import re
from datetime import datetime
from pprint import pprint
from pprint import pformat
from sgtk.platform.qt import QtGui

bundle_location = '/var/tmp'
menu_group_name = 'Menu(SG)'

# flameBatchBlessing
flame_batch_root = bundle_location
flame_batch_folder = 'flame_batch_setups'

DEBUG = True

__version__ = 'v0.0.2'

# flameAppFramework class takes care of preferences 
# and unpacking bundle to temporary location / cleanup on exit

class flameAppFramework(object):
    def __init__(self):
        self.name = self.__class__.__name__
        self._bundle_name = 'flameMenuSG'
        self._prefs = {}
        self._bundle_location = bundle_location
        self.debug = DEBUG
        try:
            import flame
            self.flame = flame
        except:
            self.flame = None
        if self.flame:
            flame_project_name = self.flame.project.current_project.name
            flame_user_name = flame.users.current_user.name
            prefs_file_name = self.bundle_name + '.' + flame_project_name + '.' + flame_user_name + '.prefs'
            self.prefs_file_location = bundle_location + os.path.sep + prefs_file_name
        else:
            self.prefs_file_location = bundle_location + os.path.sep + self.bundle_name + '.prefs'

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
        self.connector = None
        self.menu_group_name = menu_group_name
        self.debug = DEBUG
        self.dynamic_menu_data = {}

        # flame module is only avaliable when a 
        # flame project is loaded and initialized
        self.flame = None
        try:
            import flame
            self.flame = flame
        except:
            self.flame = None
        
        if not self.framework.prefs.get(self.name):
            self.prefs = {}
            self.framework.prefs[self.name] = self.prefs
        else:
            self.prefs = self.framework.prefs.get(self.name)

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
            if self.connector:
                self.connector.rescan_flag = False


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
        self.sg = None
        if not self.prefs.get('user signed out', False):
            self.log('requesting for Shotgun user')
            self.get_user()
        
        self.flame_project = None
        self.sg_linked_project = None
        self.sg_linked_project_id = None

        self.async_cache = {}
        self.async_cache_hash = hash(pformat(self.async_cache))
        self.rescan_flag = False

        self.check_sg_linked_project()
        self.update_sg_storage_root()

        self.loops = []
        self.threads = True
        self.loops.append(threading.Thread(target=self.sg_cache_loop, args=(30, )))
        
        for loop in self.loops:
            loop.daemon = True
            loop.start()
        
        self.mbox = QtGui.QMessageBox()
        
    def log(self, message):
        self.framework.log('[' + self.name + '] ' + message)

    def terminate_loops(self):
        self.threads = False
        for loop in self.loops:
            loop.join()

    def loop_timeout(self, timeout, start):
        time_passed = int(time.time() - start)
        self.log('sg_cache_loop took %s sec' % str(time.time() - start))
        if timeout <= time_passed:
            return
        else:
            self.log('sleeping for %s sec' % (timeout - time_passed))
            for n in range((timeout - time_passed) * 10):
                if not self.threads:
                    self.log('leaving loop thread: %s' % inspect.currentframe().f_back.f_code.co_name)
                    break
                time.sleep(0.1)

    # async cache related methods

    def async_cache_register(self, query, perform_query = True):
        uid = (str(uuid.uuid1()).replace('-', '')).upper()
        self.async_cache[uid] = {'query': query, 'result': []}
        if not self.sg_user:
            return uid
        if perform_query:
            entity = query.get('entity')
            filters = query.get('filters')
            fields = query.get('fields')
            self.async_cache[uid]['result'] = self.sg.find(entity, filters, fields)
        
        self.async_cache_state_check()
        return uid
    
    def async_cache_unregister(self, uid):            
        if uid in self.async_cache.keys():
            del self.async_cache[uid]
            self.rescan_flag = True
            return True
        else:
            return False

    def async_cache_get(self, uid, perform_query = False, query_type = 'result'):
        if not uid in self.async_cache.keys():
            return False
        query = self.async_cache.get(uid)
        if not query:
            return False

        if perform_query:
            entity = query.get('entity')
            filters = query.get('filters')
            fields = query.get('fields')
            self.async_cache[uid]['result'] = self.sg.find(entity, filters, fields)
        
        return query.get(query_type)

    def async_cache_clear(self):
        self.async_cache = {}
        self.rescan_flag = True
        return True

    def async_cache_state_check(self):
        if hash(pformat(self.async_cache)) != self.async_cache_hash:
            self.rescan_flag = True
            self.async_cache_hash = hash(pformat(self.async_cache))
    
    # end of async cache methods

    def sg_cache_loop(self, timeout):
        while self.threads:
            start = time.time()

            if not self.sg_user:
                self.log('no shotgun user...')
                time.sleep(1)
            else:
                results_by_hash = {}

                for cache_request_uid in self.async_cache.keys():
                    cache_request = self.async_cache.get(cache_request_uid)
                    if not cache_request:
                        continue
                    query = cache_request.get('query')
                    if not query:
                        continue
                    
                    if hash(pformat(query)) in results_by_hash.keys():
                        self.async_cache[cache_request_uid]['result'] = results_by_hash.get(hash(pformat(query)))
                    else:
                        entity = query.get('entity')
                        if not entity:
                            continue
                        filters = query.get('filters')
                        fields = query.get('fields')
                        result = self.sg.find(entity, filters, fields)
                        self.async_cache[cache_request_uid]['result'] = result
                        results_by_hash[hash(pformat(query))] = result

                self.async_cache_state_check()
                self.loop_timeout(timeout, start)

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
        self.sg = self.sg_user.create_sg_connection()
        return self.sg_user

    def clear_user(self, *args, **kwargs):
        authenticator = sgtk.authentication.ShotgunAuthenticator(sgtk.authentication.DefaultsManager())
        authenticator.clear_default_user()
        self.sg_user = None
        self.sg_human_user = None
        self.sg_user_name = None

    def check_sg_linked_project(self, *args, **kwargs):
        try:
            import flame
        except:
            self.log('no flame module avaliable to import')
            return False
        try:
            if self.flame_project != flame.project.current_project.name:
                self.log('updating flame project name: %s' % flame.project.current_project.name)
                self.flame_project = flame.project.current_project.name
        except:
            return False

        try:
            if self.sg_linked_project != flame.project.current_project.shotgun_project_name:
                self.log('updating shotgun linked project name: %s' % flame.project.current_project.shotgun_project_name)
                self.sg_linked_project = flame.project.current_project.shotgun_project_name
        except:
            return False

        if self.sg_user:
            self.log('updating project id')
            project = self.sg.find_one('Project', [['name', 'is', self.sg_linked_project.get_value()]])
            if project:
                self.sg_linked_project_id = project.get('id')

        return True

    # shotgun storage root related methods

    @property
    def sg_storage_root(self):
        return self.prefs.get('sg_storage_root', {})
    @sg_storage_root.setter
    def sg_storage_root(self, value):
        self.prefs['sg_storage_root'] = value

    def resolve_storage_root(self, path_cache_storage):
        local_file_storages = self.get_local_file_storages()
        for local_file_storage in local_file_storages:
            if local_file_storage.get('id') == path_cache_storage.get('id'):
                return self.resolve_storage_root_path(local_file_storage)
        return None

    def resolve_storage_root_path(self, path_cache_storage):
        if sys.platform == 'darwin':
            platform_path_field = 'mac_path'
        elif sys.startswith('linux'):
            platform_path_field = 'linux_path'
        else:
             message = 'Cannot resolve storage roots - unsupported platform:'
             message += sys.platform
             self.mbox.setText(message)
             self.mbox.exec_()
             return False
        
        if not path_cache_storage:
            return None
        return path_cache_storage.get(platform_path_field)

    def get_storage_root_dialog(self):
        from PySide2 import QtWidgets, QtCore
        window = None
        storage_root_paths = None
        sg_storage_data = self.get_local_file_storages()
        self.sg_storage_index = 0
        return_value = False

        if not sg_storage_data:
            message = '<p align = "center">'
            message += 'No Local File Storage(s) defined in Shotgun.<br><br>'
            message += '<i>(Click on arrow at the upper right corner of your Shotgun website ' 
            message += 'next to user icon and choose Site Preferences -> File Management to create one)</i><br>'
            mbox = QtGui.QMessageBox()
            mbox.setText(message)
            mbox.exec_()
            return False

        def combobox_changed(index):
            self.sg_storage_index = index
            storage_root_paths.setText(
                'Linux path: ' + str(sg_storage_data[self.sg_storage_index].get('linux_path')) + 
                '\nMac path: ' + str(sg_storage_data[self.sg_storage_index].get('mac_path')) +
                '\nWindows path: ' + str(sg_storage_data[self.sg_storage_index].get('windows_path'))
            )
            
        window = QtWidgets.QDialog()
        window.setMinimumSize(300, 180)
        window.setWindowTitle('Select Local File Storage')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)
        
        vbox1 = QtWidgets.QVBoxLayout()
        storage_list = QtWidgets.QComboBox(window)
        for storage in sg_storage_data:
            storage_list.addItem(storage.get('code'))
        storage_list.setCurrentIndex(self.sg_storage_index)
        storage_list.currentIndexChanged.connect(combobox_changed)
        vbox1.addWidget(storage_list)

        storage_root_paths = QtWidgets.QLabel(
            'Linux path: ' + str(sg_storage_data[self.sg_storage_index].get('linux_path')) + 
            '\nMac path: ' + str(sg_storage_data[self.sg_storage_index].get('mac_path')) +
            '\nWindows path: ' + str(sg_storage_data[self.sg_storage_index].get('windows_path')), 
            window)
        storage_root_paths.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        storage_root_paths.setStyleSheet('QFrame {color: #9a9a9a; border: 1px solid #696969 }')
        vbox1.addWidget(storage_root_paths)

        select_btn = QtWidgets.QPushButton('Select', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(100, 24)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(100, 24)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox2 = QtWidgets.QHBoxLayout()
        hbox2.addWidget(cancel_btn)
        hbox2.addWidget(select_btn)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setMargin(20)
        vbox.addLayout(vbox1)
        vbox.addLayout(hbox2)

        window.setLayout(vbox)
        if window.exec_():
            self.sg_storage_root = sg_storage_data[self.sg_storage_index]
        
        return self.sg_storage_root

    def get_local_file_storages(self):
        return self.sg.find(
            'LocalStorage',
            [],
            ['id', 'code', 'windows_path', 'linux_path', 'mac_path']
        )

    def update_sg_storage_root(self):
        sg_storage_data = self.get_local_file_storages()
        for storage in sg_storage_data:
            if storage.get('id') == self.sg_storage_root.get('id'):
                self.sg_storage_root = storage
                return True

        self.sg_storage_root = {}
        return False

class flameMenuProjectconnect(flameMenuApp):
    def __init__(self, framework, connector):
        flameMenuApp.__init__(self, framework)
        self.connector = connector

        # register async cache query
        self.active_projects_uid = self.connector.async_cache_register({
                    'entity': 'Project',
                    'filters': [['archived', 'is', False], ['is_template', 'is', False]],
                    'fields': ['name', 'tank_name']
                    })
        
    def __getattr__(self, name):
        def method(*args, **kwargs):
            project = self.dynamic_menu_data.get(name)
            if project:
                self.link_project(project)
        return method
    
    def build_menu(self):
        if not self.flame:
            return []

        flame_project_name = self.flame.project.current_project.name
        self.connector.sg_linked_project = self.flame.project.current_project.shotgun_project_name.get_value()

        menu = {'actions': []}

        if not self.connector.sg_user:
            menu['name'] = self.menu_group_name

            menu_item = {}
            menu_item['name'] = 'Sign in to Shotgun'
            menu_item['execute'] = self.sign_in
            menu['actions'].append(menu_item)
        elif self.connector.sg_linked_project:
            menu['name'] = self.menu_group_name

            menu_item = {}
            menu_item['name'] = 'Unlink from Shotgun project `' + self.connector.sg_linked_project + '`'
            menu_item['execute'] = self.unlink_project
            menu['actions'].append(menu_item)
            
            menu_item = {}
            menu_item['name'] = 'Sign Out: ' + str(self.connector.sg_user_name)
            menu_item['execute'] = self.sign_out
            menu['actions'].append(menu_item)
            
            menu_item = {}
            menu_item['name'] = 'Preferences'
            menu_item['execute'] = self.preferences_window
            menu_item['waitCursor'] = False
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
            menu_item['name'] = 'Sign Out: ' + str(self.connector.sg_user_name)
            menu_item['execute'] = self.sign_out
            menu['actions'].append(menu_item)

            menu_item = {}
            menu_item['name'] = 'Preferences'
            menu_item['execute'] = self.preferences_window
            menu_item['waitCursor'] = False
            menu['actions'].append(menu_item)

        return menu

    def get_projects(self, *args, **kwargs):
        return self.connector.async_cache_get(self.active_projects_uid)

    def unlink_project(self, *args, **kwargs):
        self.flame.project.current_project.shotgun_project_name = ''
        self.connector.sg_linked_project = None
        self.connector.sg_linked_project_id = None
        self.rescan()

    def link_project(self, project):
        project_name = project.get('name')
        if project_name:
            self.flame.project.current_project.shotgun_project_name = project_name
            self.connector.sg_linked_project = project_name
            if 'id' in project.keys():
                self.connector.sg_linked_project_id = project.get('id')
        self.rescan()

    def refresh(self, *args, **kwargs):        
        self.connector.async_cache_get(self.active_projects_uid, True)
        self.rescan()

    def sign_in(self, *args, **kwargs):
        self.connector.get_user()
        self.rescan()

    def sign_out(self, *args, **kwargs):
        self.connector.clear_user()
        self.rescan()

    def preferences_window(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore, QtGui
        
        # storage root section
        self.connector.update_sg_storage_root()
        def update_sg_storage_root_widget():
            self.connector.get_storage_root_dialog()
            storage_root.setText(self.connector.sg_storage_root.get('code'))
            storage_root_paths.setText(
            'Linux path: ' + str(self.connector.sg_storage_root.get('linux_path')) + 
            '\nMac path: ' + str(self.connector.sg_storage_root.get('mac_path')) +
            '\nWindows path: ' + str(self.connector.sg_storage_root.get('windows_path')))

        window = None
        window = QtWidgets.QDialog()
        window.setMinimumSize(800, 280)
        window.setWindowTitle(self.framework.bundle_name + ' Preferences')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-400, (screen_res.height() / 2)-180)

        hbox_storage = QtWidgets.QHBoxLayout()
        storage_root_btn = QtWidgets.QPushButton('Change Local File Storage', window)
        storage_root_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        storage_root_btn.setMinimumSize(199, 24)
        storage_root_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        storage_root_btn.clicked.connect(update_sg_storage_root_widget)
        hbox_storage.addWidget(storage_root_btn, alignment = QtCore.Qt.AlignLeft)

        storage_name = QtWidgets.QLabel('Current storage:', window)
        hbox_storage.addWidget(storage_name, alignment = QtCore.Qt.AlignLeft)

        storage_root = QtWidgets.QLabel(self.connector.sg_storage_root.get('code'), window)
        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        storage_root.setFont(boldFont)
        hbox_storage.addWidget(storage_root, alignment = QtCore.Qt.AlignRight)

        vbox1 = QtWidgets.QVBoxLayout()
        vbox1.setAlignment(QtCore.Qt.AlignTop)
        vbox1.addLayout(hbox_storage)

        storage_root_paths = QtWidgets.QLabel(
            'Linux path: ' + str(self.connector.sg_storage_root.get('linux_path')) + 
            '\nMac path: ' + str(self.connector.sg_storage_root.get('mac_path')) +
            '\nWindows path: ' + str(self.connector.sg_storage_root.get('windows_path')), 
            window)
        storage_root_paths.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        storage_root_paths.setStyleSheet('QFrame {color: #9a9a9a; border: 1px solid #696969 }')
        vbox1.addWidget(storage_root_paths)

        dummy = QtWidgets.QLabel('Not yet implemented', window)
        dummy.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        dummy.setStyleSheet('QFrame {color: #9a9a9a; border: 1px solid #696969 }')

        close_btn = QtWidgets.QPushButton('Close', window)
        close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        close_btn.setMinimumSize(88, 24)
        close_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        close_btn.clicked.connect(window.accept)

        hbox1 = QtWidgets.QHBoxLayout()
        hbox1.addLayout(vbox1)
        hbox1.addWidget(dummy)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setMargin(20)
        vbox.addLayout(hbox1)
        vbox.addWidget(close_btn, alignment = QtCore.Qt.AlignRight)

        window.setLayout(vbox)
        window.exec_()


class flameBatchBlessing(flameMenuApp):
    def __init__(self, framework):
        flameMenuApp.__init__(self, framework)
        if self.flame:
            self.root_folder = self.batch_setup_root_folder()

    def batch_setup_root_folder(self):
        try:
            import flame
        except:
            return False

        current_project_name = flame.project.current_project.name
        flame_batch_path = os.path.join(
                                    flame_batch_root,
                                    current_project_name,
                                    flame_batch_folder
                                    )
        
        if not os.path.isdir(flame_batch_path):
            try:
                os.makedirs(flame_batch_path)
                self.log('creating %s' % flame_batch_path)
            except:
                print ('PYTHON\t: %s can not create %s' % (self.framework.bundle_name, flame_batch_path))
                return False
        return flame_batch_path

    def collect_clip_uids(self, render_dest):
        import flame
        # collects clip uids from locations specified in render_dest dictionary
        # returns:    dictionary of lists of clip uid's at the locations specified
        #            in render_dest dictionary.
        #            clip_uids = {
        #                        'Batch Reels': {
        #                            'BatchReel Name': [uid1, uid2]
        #                            }
        #                        'Batch Shelf Reels': {
        #                            'Shelf Reel Name 1': [uid3, uid4]
        #                            'Shelf Reel Name 2': [uid5, uid6, uid7]
        #                            }
        #                        'Libraries': {
        #                            'Library Name 3': [uid8, uid9]
        #                        }
        #                        'Reel Groups': {
        #                            'Reel Group Name 1': {
        #                                'Reel 1': []
        #                                'Reel 2: []
        #                            }
        #                            'Reel Group Name 2': {
        #                                'Reel 1': []
        #                                'Reel 2: []
        #                            }
        #
        #                        }
        #            }

        collected_uids = dict()
        for dest in render_dest.keys():
            if dest == 'Batch Reels':
                render_dest_names = list(render_dest.get(dest))
                if not render_dest_names:
                    continue
                
                batch_reels = dict()
                for reel in flame.batch.reels:
                    current_uids = list()
                    if reel.name in render_dest_names:
                        for clip in reel.clips:
                            current_uids.append(clip.uid)
                        batch_reels[reel.name] = current_uids
                collected_uids['Batch Reels'] = batch_reels

                batch_shelf_reels = dict()
                for reel in flame.batch.shelf_reels:
                    current_uids = list()
                    if reel.name in render_dest_names:
                        for clip in reel.clips:
                            current_uids.append(clip.uid)
                        batch_shelf_reels[reel.name] = current_uids
                collected_uids['Batch Shelf Reels'] = batch_shelf_reels

            elif dest == 'Libraries':
                render_dest_names = list(render_dest.get(dest))
                if not render_dest_names:
                    continue

                libraries = dict()
                current_workspace_libraries = flame.project.current_project.current_workspace.libraries           
                for library in current_workspace_libraries:
                    current_uids = list()
                    if library.name in render_dest_names:
                        for clip in library.clips:
                            current_uids.append(clip.uid)
                        libraries[library.name] = current_uids
                collected_uids['Libraries'] = libraries
                            
            elif dest == 'Reel Groups':
                render_dest_names = list(render_dest.get(dest))
                if not render_dest_names:
                    continue
                reel_groups = dict()
                current_desktop_reel_groups = flame.project.current_project.current_workspace.desktop.reel_groups
                for reel_group in current_desktop_reel_groups:
                    reels = dict()
                    if reel_group.name in render_dest_names:
                        for reel in reel_group.reels:
                            current_uids = list()
                            for clip in reel.clips:
                                current_uids.append(clip.uid)
                            reels[reel.name] = current_uids
                    reel_groups[reel_group.name] = reels
                collected_uids['Reel Groups'] = reel_groups
            
        return collected_uids

    def bless_clip(self, clip, **kwargs):
        batch_setup_name = kwargs.get('batch_setup_name')
        batch_setup_file = kwargs.get('batch_setup_file')
        blessing_string = str({'batch_file': batch_setup_file})
        for version in clip.versions:
            for track in version.tracks:
                for segment in track.segments:
                    new_comment = segment.comment + blessing_string
                    segment.comment = new_comment
                    self.log ('blessing %s with %s' % (clip.name, blessing_string))
        return True

    def bless_batch_renders(self, userData):
        import flame
        
        # finds clips that was not in the render destionations before
        # and blesses them by adding batch_setup_name to the comments

        batch_setup_name = userData.get('batch_setup_name')
        batch_setup_file = userData.get('batch_setup_file')
        render_dest_uids = userData.get('render_dest_uids')

        for dest in render_dest_uids.keys():
            previous_uids = None
            if dest == 'Batch Reels':
                batch_reels_dest = render_dest_uids.get(dest)
                for batch_reel_name in batch_reels_dest.keys():
                    previous_uids = batch_reels_dest.get(batch_reel_name)
                    for reel in flame.batch.reels:
                        if reel.name == batch_reel_name:
                            for clip in reel.clips:
                                if clip.uid not in previous_uids:
                                    self.bless_clip(clip, 
                                        batch_setup_name = batch_setup_name, 
                                        batch_setup_file = batch_setup_file)

            elif dest == 'Batch Shelf Reels':
                batch_shelf_reels_dest = render_dest_uids.get(dest)
                for batch_shelf_reel_name in batch_shelf_reels_dest.keys():
                    previous_uids = batch_shelf_reels_dest.get(batch_shelf_reel_name)
                    for reel in flame.batch.shelf_reels:
                        if reel.name == batch_shelf_reel_name:
                            for clip in reel.clips:
                                if clip.uid not in previous_uids:
                                    self.bless_clip(clip, 
                                        batch_setup_name = batch_setup_name,
                                        batch_setup_file = batch_setup_file)

            elif dest == 'Libraries':
                libraries_dest = render_dest_uids.get(dest)
                current_workspace_libraries = flame.project.current_project.current_workspace.libraries
                for library_name in libraries_dest.keys():
                    previous_uids = libraries_dest.get(library_name)
                    for library in current_workspace_libraries:
                        if library.name == library_name:
                            for clip in library.clips:
                                if clip.uid not in previous_uids:
                                    try:
                                        self.bless_clip(clip, 
                                            batch_setup_name = batch_setup_name,
                                            batch_setup_file = batch_setup_file)
                                    except:
                                        print ('PYTHON\t: %s unable to bless %s' % (self.framework.bundle_name, clip.name))
                                        print ('PYTHON\t: %s libraries are protected from editing' % self.framework.bundle_name)
                                        continue

            elif dest == 'Reel Groups':
                reel_grous_dest = render_dest_uids.get(dest)
                current_desktop_reel_groups = flame.project.current_project.current_workspace.desktop.reel_groups
                for reel_group_name in reel_grous_dest.keys():
                    for desktop_reel_group in current_desktop_reel_groups:
                        if desktop_reel_group.name == reel_group_name:
                            reels = reel_grous_dest[reel_group_name]
                            for reel_name in reels.keys():
                                previous_uids = reels.get(reel_name)
                                for reel in desktop_reel_group.reels:
                                    if reel.name == reel_name:
                                        for clip in reel.clips:
                                            if clip.uid not in previous_uids:
                                                self.bless_clip(clip, 
                                                    batch_setup_name = batch_setup_name,
                                                    batch_setup_file = batch_setup_file)

    def create_batch_uid(self):
        # generates UUID for the batch setup

        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
        timestamp = (datetime.now()).strftime('%y%m%d%H%M')
        return timestamp + uid[:1]


class flameMenuNewBatch(flameMenuApp):
    def __init__(self, framework, connector):
        # app configuration settings
        self.steps_to_ignore = [
            'step_one',
            'step_two'
        ]
        self.types_to_include = [
            'Image Sequence',
            'Flame Render'
        ]

        # app constructor
        flameMenuApp.__init__(self, framework)
        self.connector = connector
        self.current_tasks_uid = None
        self.register_query()

        if not self.prefs:
            self.prefs['show_all'] = False
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 128

    def __getattr__(self, name):
        def method(*args, **kwargs):
            entity = self.dynamic_menu_data.get(name)
            if entity:
                self.create_new_batch(entity)
        return method

    def build_menu(self):
        '''
        # ---------------------------------
        # menu time debug code

        number_of_menu_itmes = 256
        menu = {'name': self.name, 'actions': []}
        for i in xrange(1, number_of_menu_itmes+1):
            menu['actions'].append({
                'name': 'Test selection ' + str(i),
                # 'isVisible': self.scope_reel,
                'execute': getattr(self, 'menu_item_' + str(i))
            })
        return menu

        # ---------------------------------
        # menu time debug code
        '''

        if not self.connector.sg_user:
            return None
        if not self.connector.sg_linked_project:
            return None
        if not self.flame:
            return []

        flame_project_name = self.flame.project.current_project.name
        batch_groups = []
        for batch_group in self.flame.project.current_project.current_workspace.desktop.batch_groups:
            batch_groups.append(batch_group.name.get_value())

        menu = {'actions': []}
        menu['name'] = self.menu_group_name + ' Create new batch:'
        
        menu_item = {}
        menu_item['name'] = '~ Rescan'
        menu_item['execute'] = self.rescan
        menu['actions'].append(menu_item)

        menu_item = {}
        if self.prefs['show_all']:            
            menu_item['name'] = '~ Show Assigned Only'
        else:
            menu_item['name'] = '~ Show All Avaliable'
        menu_item['execute'] = self.flip_assigned
        menu['actions'].append(menu_item)

        user_only = not self.prefs['show_all']
        filter_out = ['Project', 'Sequence']
        found_entities = self.get_entities(user_only, filter_out)

        menu_ctrls_len = len(menu)
        menu_lenght = menu_ctrls_len
        menu_lenght += len(found_entities.keys())
        for entity_type in found_entities.keys():
            menu_lenght += len(found_entities.get(entity_type))
        max_menu_lenght = self.prefs.get('menu_max_items_per_page')

        menu_main_body = []
        for index, entity_type in enumerate(sorted(found_entities.keys())):
            menu_item = {}
            menu_item['name'] = '- [ ' + entity_type + 's ]'
            menu_item['execute'] = self.rescan
            menu_main_body.append(menu_item)
            entities_by_name = {}
            for entity in found_entities[entity_type]:
                entities_by_name[entity.get('name')] = entity
            for entity_name in sorted(entities_by_name.keys()):
                entity = entities_by_name.get(entity_name)
                menu_item = {}
                if entity.get('name') in batch_groups:
                    menu_item['name'] = '  * ' + entity.get('name')
                else:
                    menu_item['name'] = '     ' + entity.get('name')

                self.dynamic_menu_data[str(id(entity))] = entity
                menu_item['execute'] = getattr(self, str(id(entity)))
                menu_main_body.append(menu_item)

        if menu_lenght < max_menu_lenght:
        # controls and entites fits within menu size
        # we do not need additional page switch controls
            for menu_item in menu_main_body:
                menu['actions'].append(menu_item)

        else:
            # round up number of pages and get current page
            num_of_pages = ((menu_lenght) + max_menu_lenght - 1) // max_menu_lenght
            curr_page = self.prefs.get('current_page')
            
            # decorate top with move backward control
            # if we're not on the first page
            if curr_page > 0:
                menu_item = {}
                menu_item['name'] = '<<[ prev page ' + str(curr_page) + ' of ' + str(num_of_pages) + ' ]'
                menu_item['execute'] = self.page_bkw
                menu['actions'].append(menu_item)

            # calculate the start and end position of a window
            # and append items to the list
            menu_used_space = menu_ctrls_len + 2 # two more controls for page flip
            window_size = max_menu_lenght - menu_used_space
            start_index = window_size*curr_page + min(1*curr_page, 1)
            end_index = window_size*curr_page+window_size + ((curr_page+1) // num_of_pages)

            for menu_item in menu_main_body[start_index:end_index]:
                menu['actions'].append(menu_item)
            
            # decorate bottom with move forward control
            # if we're not on the last page            
            if curr_page < (num_of_pages - 1):
                menu_item = {}
                menu_item['name'] = '[ next page ' + str(curr_page+2) + ' of ' + str(num_of_pages) + ' ]>>'
                menu_item['execute'] = self.page_fwd
                menu['actions'].append(menu_item)

        for action in menu['actions']:
            action['isVisible'] = self.scope_desktop

        return menu

    def get_entities(self, user_only = True, filter_out=[]):
        current_tasks = self.connector.async_cache_get(self.current_tasks_uid)
        if not current_tasks:
            return {}

        tasks = []
        if user_only:
            for task in current_tasks:
                task_assignees = task.get('task_assignees')
                for task_assignee in task_assignees:
                    if task_assignee.get('id') == self.connector.sg_human_user.get('id'):
                        tasks.append(task)
        else:
            tasks = list(current_tasks)

        entities = {}
        for task in tasks:
            if task['entity']:
                task_entity_type = task['entity']['type']
                if task_entity_type in filter_out:
                    continue
                task_entity_id = task['entity']['id']
                if task_entity_type not in entities.keys():
                    entities[task_entity_type] = {}
                entities[task_entity_type][task_entity_id] = task['entity']

        for entity_type in entities.keys():
            entities[entity_type] = entities[entity_type].values()

        return entities

    def create_new_batch(self, entity):        
        sg = self.connector.sg_user.create_sg_connection()
        entity = sg.find_one (
            entity.get('type'),
            [['id', 'is', entity.get('id')]],
            ['code', 'sg_head_in', 'sg_tail_out', 'sg_vfx_requirements']
        )

        publishes = sg.find (
            'PublishedFile',
            [['entity', 'is', {'id': entity.get('id'), 'type': entity.get('type')}]],
            [
                'path_cache',
                'path_cache_storage',
                'name',
                'version_number',
                'published_file_type',
                'version.Version.code',
                'task.Task.step.Step.code',
                'task.Task.step.Step.short_name'
            ]
        )

        publishes_to_import = []
        publishes_by_step = {}
        for publish in publishes:
            step_short_name = publish.get('task.Task.step.Step.short_name')
            if step_short_name in self.steps_to_ignore:
                continue
            if step_short_name not in publishes_by_step.keys():
                publishes_by_step[step_short_name] = []
            published_file_type = publish.get('published_file_type')
            if published_file_type:
                published_file_type_name = published_file_type.get('name')
            if published_file_type_name in self.types_to_include:
                publishes_by_step[step_short_name].append(publish)
        

        for step in publishes_by_step.keys():
            step_group = publishes_by_step.get(step)
            names_group = dict()
            
            for publish in step_group:
                name = publish.get('name')
                if name not in names_group.keys():
                    names_group[name] = []
                names_group[name].append(publish)
            
            for name in names_group.keys():
                version_numbers = []
                for publish in names_group[name]:
                    version_number = publish.get('version_number')
                    version_numbers.append(version_number)
                max_version = max(version_numbers)
                for publish in names_group[name]:
                    version_number = publish.get('version_number')
                    if version_number == max_version:
                        publishes_to_import.append(publish)
        
        flame_paths_to_import = []
        for publish in publishes_to_import:
            path_cache = publish.get('path_cache')
            if not path_cache:
                continue            
            storage_root = self.connector.resolve_storage_root(publish.get('path_cache_storage'))
            if not storage_root:
                continue
            path = os.path.join(storage_root, path_cache)
            flame_path = self.build_flame_friendly_path(path)
            flame_paths_to_import.append(flame_path)
        
        code = entity.get('code')
        if not code:
            code = 'New Batch'

        sg_head_in = entity.get('sg_head_in')
        if not sg_head_in:
            sg_head_in = 1001
        
        sg_tail_out = entity.get('sg_tail_out')
        if not sg_tail_out:
            sg_tail_out = 1101

        sg_vfx_req = entity.get('sg_vfx_requirements')
        if not sg_vfx_req:
            sg_vfx_req = 'no requirements specified'

        dur = (sg_tail_out - sg_head_in) + 1

        self.flame.batch.create_batch_group (
            code, start_frame = 1, duration = dur
        )
        
        for flame_path in flame_paths_to_import:
            self.flame.batch.import_clip(flame_path, 'Schematic Reel 1')

        self.flame.batch.organize()

    def build_flame_friendly_path(self, path):
        import re
        import glob
        import fnmatch

        file_names = os.listdir(os.path.dirname(path))
        if not file_names:
            return None
        frame_pattern = re.compile(r"^(.+?)([0-9#]+|[%]0\dd)$")
        root, ext = os.path.splitext(os.path.basename(path))
        match = re.search(frame_pattern, root)
        if not match:
            return None
        pattern = os.path.join("%s%s" % (re.sub(match.group(2), "*", root), ext))
        files = []
        for file_name in file_names:
            if fnmatch.fnmatch(file_name, pattern):
                files.append(os.path.join(os.path.dirname(path), file_name))
        if not files:
            return None
        file_roots = [os.path.splitext(f)[0] for f in files]
        frame_padding = len(re.search(frame_pattern, file_roots[0]).group(2))
        offset = len(match.group(1))

        # consitency check
        frames = []
        for f in file_roots:
            try:
                frame = int(os.path.basename(f)[offset:offset+frame_padding])
            except:
                continue
            frames.append(frame)
        if not frames:
            return None
        min_frame = min(frames)
        max_frame = max(frames)
        if ((max_frame + 1) - min_frame) != len(frames):
            # report what exactly are missing
            current_frame = min_frame
            for frame in frames:
                if not current_frame in frames:
                    # report logic to be placed here
                    pass
                current_frame += 1
            return None
        
        format_str = "[%%0%sd-%%0%sd]" % (
                frame_padding,
                frame_padding
            )
        
        frame_spec = format_str % (min_frame, max_frame)
        file_name = "%s%s%s" % (match.group(1), frame_spec, ext)

        return os.path.join(
                    os.path.dirname (path),
                    file_name
                    )

    def scope_desktop(self, selection):
        for item in selection:
            if isinstance(item, (self.flame.PyDesktop)):
                return True
        return False

    def flip_assigned(self, *args, **kwargs):
        self.prefs['show_all'] = not self.prefs['show_all']
        # self.rescan()

    def page_fwd(self, *args, **kwargs):
        self.prefs['current_page'] += 1

    def page_bkw(self, *args, **kwargs):
        self.prefs['current_page'] = max(self.prefs['current_page'] - 1, 0)

    def register_query(self, *args, **kwargs):
        if self.connector.sg_linked_project_id and self.current_tasks_uid:
            # check if project id match
            try:
                filters = self.connector.async_cache.get(self.current_tasks_uid).get('query').get('filters')
                project_id = filters[0][2]
            except:
                return False

            if project_id != self.connector.sg_linked_project_id:
                # unregiter old id and register new one
                self.connector.async_cache_unregister(self.current_tasks_uid)
                self.current_tasks_uid = self.connector.async_cache_register({
                    'entity': 'Task',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': ['entity', 'task_assignees']
                })
                return True
            else:
                return False
            
        elif self.connector.sg_linked_project_id and not self.current_tasks_uid:
            # register new query from scratch
            self.current_tasks_uid = self.connector.async_cache_register({
                    'entity': 'Task',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': ['entity', 'task_assignees']
            })
            return True
        elif self.current_tasks_uid and not self.connector.sg_linked_project_id:
            # unregister current uid
            self.connector.async_cache_unregister(self.current_tasks_uid)
            return True
        else:
            return False


class flameMenuBatchLoader(flameMenuApp):
    def __init__(self, framework, connector):
        self.types_to_include = [
            'Image Sequence',
            'Flame Render'
        ]

        flameMenuApp.__init__(self, framework)
        self.connector = connector

        if not self.prefs:
            self.prefs['show_all'] = False
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 64

    def __getattr__(self, name):
        def method(*args, **kwargs):
            entity = self.dynamic_menu_data.get(name)
            if entity:
                if entity.get('caller') == 'build_addremove_menu':
                    self.update_loader_list(entity)
                elif entity.get('caller') == 'build_batch_loader_menu':
                    self.load_into_batch(entity)
            self.rescan()
        return method

    def build_menu(self):
        if not self.connector.sg_user:
            return None
        if not self.connector.sg_linked_project:
            return None

        batch_name = self.flame.batch.name.get_value()
        if ('additional menu ' + batch_name) in self.prefs.keys():
            add_menu_list = self.prefs.get('additional menu ' + batch_name)
        else:
            self.prefs['additional menu ' + batch_name] = []
            sg = self.connector.sg_user.create_sg_connection()
            project_id = self.connector.sg_linked_project_id
            task_filters = [['project.Project.id', 'is', project_id]]
            tasks = sg.find('Task',
                task_filters,
                ['entity']
            )
            for task in tasks:
                entity = task.get('entity')
                if entity:
                    if entity.get('name') == batch_name:
                        break
            if entity:
                self.update_loader_list(entity)
            add_menu_list = self.prefs.get('additional menu ' + batch_name)

        menus = []
        menus.append(self.build_addremove_menu())

        for entity in add_menu_list:
            batch_loader_menu = self.build_batch_loader_menu(entity)
            if batch_loader_menu:
                menus.append(batch_loader_menu)

        return menus

    def build_addremove_menu(self):
        if not self.connector.sg_user:
            return None
        if not self.connector.sg_linked_project:
            return None

        flame_project_name = self.flame.project.current_project.name
        batch_name = self.flame.batch.name.get_value()
        entities_to_mark = []
        batch_loader_additional = self.prefs.get('additional menu ' + batch_name)
        for item in batch_loader_additional:
            entities_to_mark.append(item.get('id'))

        menu = {'actions': []}
        menu['name'] = self.menu_group_name + ' Add/Remove'

        menu_item = {}
        menu_item['name'] = '~ Rescan'
        menu_item['execute'] = self.rescan
        menu['actions'].append(menu_item)

        menu_item = {}
        if self.prefs['show_all']:            
            menu_item['name'] = '~ Show Assigned Only'
        else:
            menu_item['name'] = '~ Show All Avaliable'
        menu_item['execute'] = self.flip_assigned
        menu['actions'].append(menu_item)

        user_only = not self.prefs['show_all']
        filter_out = ['Project', 'Sequence']
        found_entities = self.get_entities(user_only, filter_out)

        menu_ctrls_len = len(menu)
        menu_lenght = menu_ctrls_len
        menu_lenght += len(found_entities.keys())
        for entity_type in found_entities.keys():
            menu_lenght += len(found_entities.get(entity_type))
        max_menu_lenght = self.prefs.get('menu_max_items_per_page')

        menu_main_body = []
        for index, entity_type in enumerate(sorted(found_entities.keys())):
            menu_item = {}
            menu_item['name'] = '- [ ' + entity_type + 's ]'
            menu_item['execute'] = self.rescan
            menu_main_body.append(menu_item)
            entities_by_name = {}
            for entity in found_entities[entity_type]:
                entities_by_name[entity.get('code')] = entity
            for entity_name in sorted(entities_by_name.keys()):
                entity = entities_by_name.get(entity_name)
                menu_item = {}
                if entity.get('id') in entities_to_mark:
                    menu_item['name'] = '  * ' + entity.get('code')
                else:
                    menu_item['name'] = '     ' + entity.get('code')

                entity['caller'] = inspect.currentframe().f_code.co_name
                self.dynamic_menu_data[str(id(entity))] = entity
                menu_item['execute'] = getattr(self, str(id(entity)))
                menu_main_body.append(menu_item)

        if menu_lenght < max_menu_lenght:
        # controls and entites fits within menu size
        # we do not need additional page switch controls
            for menu_item in menu_main_body:
                menu['actions'].append(menu_item)

        else:
            # round up number of pages and get current page
            num_of_pages = ((menu_lenght) + max_menu_lenght - 1) // max_menu_lenght
            curr_page = self.prefs.get('current_page')
            
            # decorate top with move backward control
            # if we're not on the first page
            if curr_page > 0:
                menu_item = {}
                menu_item['name'] = '<<[ prev page ' + str(curr_page) + ' of ' + str(num_of_pages) + ' ]'
                menu_item['execute'] = self.page_bkw
                menu['actions'].append(menu_item)

            # calculate the start and end position of a window
            # and append items to the list
            menu_used_space = menu_ctrls_len + 2 # two more controls for page flip
            window_size = max_menu_lenght - menu_used_space
            start_index = window_size*curr_page + min(1*curr_page, 1)
            end_index = window_size*curr_page+window_size + ((curr_page+1) // num_of_pages)

            for menu_item in menu_main_body[start_index:end_index]:
                menu['actions'].append(menu_item)
            
            # decorate bottom with move forward control
            # if we're not on the last page            
            if curr_page < (num_of_pages - 1):
                menu_item = {}
                menu_item['name'] = '[ next page ' + str(curr_page+2) + ' of ' + str(num_of_pages) + ' ]>>'
                menu_item['execute'] = self.page_fwd
                menu['actions'].append(menu_item)

        return menu

    def build_batch_loader_menu(self, entity):
        sg = self.connector.sg_user.create_sg_connection()
        entity_type = entity.get('type')
        entity_id = entity.get('id')
        publishes = sg.find(
            'PublishedFile',
            [['entity', 'is', {'id': entity_id, 'type': entity_type}]],
            [
                'path_cache',
                'path_cache_storage',
                'name',
                'version_number',
                'published_file_type',
                'version.Version.code',
                'task.Task.step.Step.code',
                'task.Task.step.Step.short_name'
            ]
        )
        
        found_entity = sg.find_one(
                    entity_type,
                    [['id', 'is', entity_id]],
                    ['code']
        )

        menu = {}
        menu['name'] = found_entity.get('code') + ':'
        menu['actions'] = []

        menu_item = {}
        menu_item['name'] = '~ Rescan'
        menu_item['execute'] = self.rescan
        menu['actions'].append(menu_item)

        step_names = set()
        for publish in publishes:
            # step_name = publish.get('task.Task.step.Step.short_name')
            step_name = publish.get('task.Task.step.Step.code')
            if not step_name:
                step_name = ''
            step_names.add(step_name)

        for step_name in step_names:
            menu_item = {}
            menu_item['name'] = '- [ ' + step_name + ' ]'
            menu_item['execute'] = self.rescan
            menu['actions'].append(menu_item)
            
            published_file_type_name = ''
            for publish in publishes:
                step = publish.get('task.Task.step.Step.code')
                if not step:
                    step = ''
                if step == step_name:
                    published_file_type = publish.get('published_file_type')
                    if published_file_type:
                        published_file_type_name = published_file_type.get('name')
                    else:
                        published_file_type_name = None

                    if published_file_type_name in self.types_to_include:
                        name = publish.get('name')
                        if not name:
                            name = ''
                        name_elements = name.split(' ')
                        if name_elements[-1] == 'render':
                            name_elements[-1] = ''
                        else:
                            name_elements[-1] = ' (' + name_elements[-1] + ')'

                        display_name = publish.get('version.Version.code')
                        if not display_name:
                            display_name = name_elements[0]
                        menu_item = {}
                        menu_item['name'] = ' '*4 + display_name + name_elements[-1]
                        publish['caller'] = inspect.currentframe().f_code.co_name
                        self.dynamic_menu_data[str(id(publish))] = publish
                        menu_item['execute'] = getattr(self, str(id(publish)))
                        menu['actions'].append(menu_item)

        return menu

    def update_loader_list(self, entity):
        batch_name = self.flame.batch.name.get_value()
        add_list = self.prefs.get('additional menu ' + batch_name)
        add_list_ids = []
        entity_id = entity.get('id')
        for existing_entity in add_list:
            add_list_ids.append(existing_entity.get('id'))
        if entity_id in add_list_ids:
            for index, existing_entity in enumerate(add_list):
                if existing_entity.get('id') == entity_id:
                    add_list.pop(index)
        else:
            add_list.append(entity)
        self.prefs['additional menu ' + batch_name] = add_list

    def load_into_batch(self, entity):
        path_cache = entity.get('path_cache')
        if not path_cache:
            return
        
        storage_root = self.connector.resolve_storage_root(entity.get('path_cache_storage'))
        if not storage_root:
            return
        path = os.path.join(storage_root, path_cache)
        flame_path = self.build_flame_friendly_path(path)
        if not flame_path:
            return

        self.flame.batch.import_clip(flame_path, 'Schematic Reel 1')

    def get_entities(self, user_only = True, filter_out=[]):
        sg = self.connector.sg_user.create_sg_connection()
        project_id = self.connector.sg_linked_project_id
        task_filters = [['project.Project.id', 'is', project_id]]

        if user_only:
            human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.connector.sg_user.login]],
                []
                )
            task_filters.append(['task_assignees', 'is', human_user])

        tasks = sg.find('Task',
            task_filters,
            ['entity']
        )

        entities = {}
        for task in tasks:
            if task['entity']:
                task_entity_type = task['entity']['type']
                task_entity_id = task['entity']['id']
                if task_entity_type not in entities.keys():
                    entities[task_entity_type] = []
                entities[task_entity_type].append(task_entity_id)

        found_entities = {}
        for entity_type in entities.keys():
            if entity_type in filter_out:
                continue
            filters = ['id', 'in']
            filters.extend(entities.get(entity_type))
            found_by_type = sg.find(entity_type, 
                [ filters ],
                ['code']
            )
            found_entities[entity_type] = list(found_by_type)

        return found_entities

    def build_flame_friendly_path(self, path):
        import re
        import glob
        import fnmatch

        file_names = os.listdir(os.path.dirname(path))
        if not file_names:
            return None
        frame_pattern = re.compile(r"^(.+?)([0-9#]+|[%]0\dd)$")
        root, ext = os.path.splitext(os.path.basename(path))
        match = re.search(frame_pattern, root)
        if not match:
            return None
        pattern = os.path.join("%s%s" % (re.sub(match.group(2), "*", root), ext))
        files = []
        for file_name in file_names:
            if fnmatch.fnmatch(file_name, pattern):
                files.append(os.path.join(os.path.dirname(path), file_name))
        if not files:
            return None
        file_roots = [os.path.splitext(f)[0] for f in files]
        frame_padding = len(re.search(frame_pattern, file_roots[0]).group(2))
        offset = len(match.group(1))

        # consitency check
        frames = []
        for f in file_roots:
            try:
                frame = int(os.path.basename(f)[offset:offset+frame_padding])
            except:
                continue
            frames.append(frame)
        if not frames:
            return None
        min_frame = min(frames)
        max_frame = max(frames)
        if ((max_frame + 1) - min_frame) != len(frames):
            # report what exactly are missing
            current_frame = min_frame
            for frame in frames:
                if not current_frame in frames:
                    # report logic to be placed here
                    pass
                current_frame += 1
            return None
        
        format_str = "[%%0%sd-%%0%sd]" % (
                frame_padding,
                frame_padding
            )
        
        frame_spec = format_str % (min_frame, max_frame)
        file_name = "%s%s%s" % (match.group(1), frame_spec, ext)

        return os.path.join(
                    os.path.dirname (path),
                    file_name
                    )

    def flip_assigned(self, *args, **kwargs):
        self.prefs['show_all'] = not self.prefs['show_all']
        self.rescan()

    def page_fwd(self, *args, **kwargs):
        self.prefs['current_page'] += 1

    def page_bkw(self, *args, **kwargs):
        self.prefs['current_page'] = max(self.prefs['current_page'] - 1, 0)

    def refresh(self, *args, **kwargs):
        pass

    def rescan(self, *args, **kwargs):
        self.refresh()
        self.framework.rescan()


class flameMenuPublisher(flameMenuApp):
    def __init__(self, framework, connector):
        # app configuration settings (to be moved to preferences)
        self.flame_bug_message = True
        self.templates = {
            # known tokens are {Sequence},{Shot},{Step},{name},{version},{version_four},{frame}
            # {name} and {version} will be guessed from the clip name and taken from
            # number of Batch itertations as a fallback.
            # EXAMPLE: There are 9 batch iterations in batch group.
            # Any of the clips named as "mycomp", "SHOT_001_mycomp", "SHOT_001_mycomp_009", "SHOT_001_mycomp_v009"
            # Would give us "mycomp" as a {name} and 009 as {version}
            # Version number padding are default to 3 at the moment, ### style padding is not yet implemented
            # Publishing into asset will just replace {Shot} fied with asset name
            # 'flame_image_sequence': 'sequences/{Sequence}/{Shot}/{Step}/publish/{Shot}_{name}_v{version}/{Shot}_{name}_v{version}.{frame}.{ext}',
            # 'flame_movie': 'sequences/{Sequence}/{Shot}/{Step}/publish/{Shot}_{name}_v{version}/{Shot}_{name}_v{version}.{frame}.mov',
            'flame_render': 'sequences/{Sequence}/{Shot}/{Step}/publish/{Shot}_{name}_v{version}/{Shot}_{name}_v{version}.{frame}.exr',
            'flame_batch': 'sequences/{Sequence}/{Shot}/{Step}/publish/flame_batch/{Shot}_{name}_v{version}.batch',
            'version_name': '{Shot}_{name}_v{version}'
        }
        self.flame_render_type = 'Flame Render'
        self.flame_batch_type = 'Flame Batch File'
        self.poster_frame = 1

        # app constructor
        flameMenuApp.__init__(self, framework)
        self.connector = connector
        if not self.prefs:
            self.prefs['show_all'] = False
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 64
            self.prefs['flame_bug_message_shown'] = False
        self.selected_clips = []
        self.mbox = QtGui.QMessageBox()
        
    def __getattr__(self, name):
        def method(*args, **kwargs):
            entity = self.dynamic_menu_data.get(name)
            if entity:
                if entity.get('caller') == 'build_addremove_menu':
                    self.show_bug_message()
                    self.update_loader_list(entity)
                elif entity.get('caller') == 'flip_assigned_for_entity':
                    self.show_bug_message()
                    self.flip_assigned_for_entity(entity)
                elif entity.get('caller') == 'publish':
                    self.publish(entity, args[0])
            self.rescan()
        return method

    def create_uid(self):
        '''
        generates UUID for the batch setup
        '''
        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
        # timestamp = (datetime.now()).strftime('%y%m%d%H%M')
        return uid[:4]

    def scope_clip(self, selection):
        selected_clips = []
        visibility = False
        for item in selection:
            if isinstance(item, (self.flame.PyClip)):
                selected_clips.append(item)
                visibility = True
        return visibility

    def build_menu(self):
        if not self.connector.sg_user:
            return None
        if not self.connector.sg_linked_project:
            return None

        batch_name = self.flame.batch.name.get_value()
        if ('additional menu ' + batch_name) in self.prefs.keys():
            add_menu_list = self.prefs.get('additional menu ' + batch_name)
        else:
            self.prefs['additional menu ' + batch_name] = []
            sg = self.connector.sg_user.create_sg_connection()
            project_id = self.connector.sg_linked_project_id
            task_filters = [['project.Project.id', 'is', project_id]]
            tasks = sg.find('Task',
                task_filters,
                ['entity']
            )
            entity = {}
            for task in tasks:
                entity = task.get('entity')
                if entity:
                    if entity.get('name') == batch_name:
                        break
            if entity:
                self.update_loader_list(entity)
            add_menu_list = self.prefs.get('additional menu ' + batch_name)

        menus = []
        add_remove_menu = self.build_addremove_menu()
        for action in add_remove_menu['actions']:
            action['isVisible'] = self.scope_clip
        menus.append(add_remove_menu)

        for entity in add_menu_list:
            publish_menu = self.build_publish_menu(entity)
            if publish_menu:
                for action in publish_menu['actions']:
                    action['isVisible'] = self.scope_clip
                menus.append(publish_menu)

        return menus

    def build_addremove_menu(self):
        if not self.connector.sg_user:
            return None
        if not self.connector.sg_linked_project:
            return None

        flame_project_name = self.flame.project.current_project.name
        batch_name = self.flame.batch.name.get_value()
        entities_to_mark = []
        batch_loader_additional = self.prefs.get('additional menu ' + batch_name)
        for item in batch_loader_additional:
            entities_to_mark.append(item.get('id'))

        menu = {'actions': []}
        menu['name'] = self.menu_group_name + ' Add/Remove'

        menu_item = {}
        menu_item['name'] = '~ Rescan'
        menu_item['execute'] = self.rescan
        menu['actions'].append(menu_item)

        menu_item = {}
        if self.prefs['show_all']:            
            menu_item['name'] = '~ Show Assigned Only'
        else:
            menu_item['name'] = '~ Show All'
        menu_item['execute'] = self.flip_assigned
        menu['actions'].append(menu_item)

        user_only = not self.prefs['show_all']
        filter_out = ['Project', 'Sequence']
        found_entities = self.get_entities(user_only, filter_out)

        if len(found_entities) == 0:
            menu_item = {}
            menu_item['name'] = ' '*4 + 'No assigned tasks found'
            menu_item['execute'] = self.rescan
            menu_item['isEnabled'] = False
            menu['actions'].append(menu_item)

        menu_ctrls_len = len(menu)
        menu_lenght = menu_ctrls_len
        menu_lenght += len(found_entities.keys())
        for entity_type in found_entities.keys():
            menu_lenght += len(found_entities.get(entity_type))
        max_menu_lenght = self.prefs.get('menu_max_items_per_page')

        menu_main_body = []
        for index, entity_type in enumerate(sorted(found_entities.keys())):
            menu_item = {}
            menu_item['name'] = '- [ ' + entity_type + 's ]'
            menu_item['execute'] = self.rescan
            menu_main_body.append(menu_item)
            entities_by_name = {}
            for entity in found_entities[entity_type]:
                entities_by_name[entity.get('code')] = entity
            for entity_name in sorted(entities_by_name.keys()):
                entity = entities_by_name.get(entity_name)
                menu_item = {}
                if entity.get('id') in entities_to_mark:
                    menu_item['name'] = '  * ' + entity.get('code')
                else:
                    menu_item['name'] = '     ' + entity.get('code')

                entity['caller'] = inspect.currentframe().f_code.co_name
                self.dynamic_menu_data[str(id(entity))] = entity
                menu_item['execute'] = getattr(self, str(id(entity)))
                menu_main_body.append(menu_item)

        if menu_lenght < max_menu_lenght:
        # controls and entites fits within menu size
        # we do not need additional page switch controls
            for menu_item in menu_main_body:
                menu['actions'].append(menu_item)

        else:
            # round up number of pages and get current page
            num_of_pages = ((menu_lenght) + max_menu_lenght - 1) // max_menu_lenght
            curr_page = self.prefs.get('current_page')
            
            # decorate top with move backward control
            # if we're not on the first page
            if curr_page > 0:
                menu_item = {}
                menu_item['name'] = '<<[ prev page ' + str(curr_page) + ' of ' + str(num_of_pages) + ' ]'
                menu_item['execute'] = self.page_bkw
                menu['actions'].append(menu_item)

            # calculate the start and end position of a window
            # and append items to the list
            menu_used_space = menu_ctrls_len + 2 # two more controls for page flip
            window_size = max_menu_lenght - menu_used_space
            start_index = window_size*curr_page + min(1*curr_page, 1)
            end_index = window_size*curr_page+window_size + ((curr_page+1) // num_of_pages)

            for menu_item in menu_main_body[start_index:end_index]:
                menu['actions'].append(menu_item)
            
            # decorate bottom with move forward control
            # if we're not on the last page            
            if curr_page < (num_of_pages - 1):
                menu_item = {}
                menu_item['name'] = '[ next page ' + str(curr_page+2) + ' of ' + str(num_of_pages) + ' ]>>'
                menu_item['execute'] = self.page_fwd
                menu['actions'].append(menu_item)

        return menu

    def build_publish_menu(self, entity):
        sg = self.connector.sg_user.create_sg_connection()

        entity_type = entity.get('type')
        entity_id = entity.get('id')
        if entity_id not in self.prefs.keys():
            self.prefs[entity_id] = {}
            self.prefs[entity_id]['show_all'] = False
        prefs = self.prefs.get(entity_id)
        
        tasks = sg.find(
            'Task',
            [['entity', 'is', {'id': entity_id, 'type': entity_type}]],
            [
                'content',
                'step.Step.code',
                'step.Step.short_name',
                'task_assignees',
                'project.Project.id',
                'entity'
            ]
        )

        versions = sg.find(
            'Version',
            [['entity', 'is', {'id': entity_id, 'type': entity_type}]],
            [
                'code',
                'sg_task.Task.id'
            ]
        )
        
        found_entity = sg.find_one(
                    entity_type,
                    [['id', 'is', entity_id]],
                    ['code']
        )

        human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.connector.sg_user.login]],
                []
                )

        menu = {}
        menu['name'] = 'Publish ' + found_entity.get('code') + ':'
        menu['actions'] = []

        menu_item = {}
        menu_item['name'] = '~ Rescan'
        menu_item['execute'] = self.rescan
        menu['actions'].append(menu_item)

        menu_item = {}        
        show_all_entity = {}
        show_all_entity['caller'] = 'flip_assigned_for_entity'
        show_all_entity['id'] = entity_id

        if self.prefs[entity_id]['show_all']:            
            menu_item['name'] = '~ Show Assigned Only'
        else:
            menu_item['name'] = '~ Show All Tasks'

        self.dynamic_menu_data[str(id(show_all_entity))] = show_all_entity
        menu_item['execute'] = getattr(self, str(id(show_all_entity)))
        menu['actions'].append(menu_item)

        tasks_by_step = {}
        for task in tasks:
            task_assignees = task.get('task_assignees')
            user_ids = []
            if task_assignees:
                for user in task_assignees:
                    user_ids.append(user.get('id'))
            if not prefs['show_all']:
                if human_user.get('id') not in user_ids:
                    continue

            step_name = task.get('step.Step.code')
            if not step_name:
                step_name = ''
            if step_name not in tasks_by_step.keys():
                tasks_by_step[step_name] = []
            tasks_by_step[step_name].append(task)
        
        if len(tasks_by_step.values()) == 0:
            menu_item = {}
            menu_item['name'] = ' '*4 + 'No assigned tasks found'
            menu_item['execute'] = self.rescan
            menu_item['isEnabled'] = False
            menu['actions'].append(menu_item)            

        for step_name in tasks_by_step.keys():
            if len(tasks_by_step[step_name]) != 1:
                menu_item = {}
                menu_item['name'] = '- [ ' + step_name + ' ]'
                menu_item['execute'] = self.rescan
                menu['actions'].append(menu_item)
            elif tasks_by_step[step_name][0].get('content') != step_name:
                menu_item = {}
                menu_item['name'] = '- [ ' + step_name + ' ]'
                menu_item['execute'] = self.rescan
                menu['actions'].append(menu_item)

            for task in tasks_by_step[step_name]:                
                task_name = task.get('content')
                menu_item = {}
                if (task_name == step_name) and (len(tasks_by_step[step_name]) == 1):
                    menu_item['name'] = '- [ ' + task_name + ' ]'
                else:
                    menu_item['name'] = ' '*4 + '- [ ' + task_name + ' ]'
                menu_item['execute'] = self.rescan
                menu['actions'].append(menu_item)

                task_id = task.get('id')
                for version in versions:
                    if task_id == version.get('sg_task.Task.id'):
                        menu_item = {}
                        menu_item['name'] = ' '*8 + '* ' + version.get('code')
                        menu_item['execute'] = self.rescan
                        menu_item['isEnabled'] = False
                        menu['actions'].append(menu_item)
                
                menu_item = {}
                menu_item['name'] = ' '*12 + 'publish to task "' + task_name + '"'
                publish_entity = {}
                publish_entity['caller'] = 'publish'
                publish_entity['task'] = task
                self.dynamic_menu_data[str(id(publish_entity))] = publish_entity
                menu_item['execute'] = getattr(self, str(id(publish_entity)))
                menu_item['waitCursor'] = False
                menu['actions'].append(menu_item)
                
        return menu

    def publish(self, entity, selection):
        
        # shotgun storage root resolution
        storage_root_path = None
        if not self.connector.sg_storage_root:
            if not self.connector.get_storage_root_dialog():
                return False
        
        self.connector.update_sg_storage_root()
        storage_root_path = self.connector.resolve_storage_root_path(self.connector.sg_storage_root)

        if not storage_root_path:
            if sys.platform == 'darwin':
                message = 'No Mac path '
            elif sys.startswith('linux'):
                platform_path_field = 'No Linux path '
            message += 'specified for Shotgun Local File Storage "'
            message += self.connector.sg_storage_root.get('code')
            message += '". Can not continue with publishing.'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        if not os.path.isdir(storage_root_path):
            message = 'Path "' + storage_root_path
            message += '" specified in Shotgun Local File Storage "'
            message += self.connector.sg_storage_root.get('code')
            message += '"  does not exist. Can not continue with publishing.'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        # start of main publishing routine
        task = entity.get('task')
        task_entity = task.get('entity')
        task_entity_type = task_entity.get('type')
        task_entity_name = task_entity.get('name')
        task_entity_id = task_entity.get('id')
        task_step = task.get('step.Step.code')
        uid = self.create_uid()
        
        sg = self.connector.sg_user.create_sg_connection()
        project_id = entity['task']['project.Project.id']
        proj = sg.find_one(
            'Project',
            [['id', 'is', project_id]],
            [
                'name',
                'tank_name'
            ]
        )

        project_folder_name = proj.get('tank_name')
        if not project_folder_name:
            project_folder_name = proj.get('name')
        
        project_root = os.path.join(storage_root_path, project_folder_name)
        if not os.path.isdir(project_root):
            message = 'project folder "'
            message += project_root
            message += '" does not exist. '
            message += 'Please create project folder to publish.'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        # we need to bootstrap toolkit here but
        # let's do a quick and dirty manual assignments
        # for now
        # multiple selections are left for later
        if len(selection) > 1:
            message = 'More than one clip selected. '
            message += 'Multiple selection publish is not yet implemented. '
            message += 'Please select one clip at time.'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        clip = selection[0]

        shot = sg.find_one(
                'Shot',
                [['id', 'is', task_entity_id]],
                ['sg_sequence']
            )
            
        sequence = shot.get('sg_sequence')
        if not sequence:
            sequence_name = 'DefaultSequence'
        else:
            sequence_name = sequence.get('name')
            if not sequence_name:
                sequence_name = 'DefaultSequence'

        # basic name/version detection from clip name
        batch_group_name = self.flame.batch.name.get_value()

        clip_name = clip.name.get_value()
        version_number = -1
        version_padding = -1
        if clip_name.startswith(batch_group_name):
            clip_name = clip_name[len(batch_group_name):]

        if clip_name[-1].isdigit():
            match = re.split('(\d+)', clip_name)
            try:
                version_number = int(match[-2])
            except:
                pass

            version_padding = len(match[-2])
            clip_name = clip_name[: -version_padding]
        
        if clip_name.endswith('v'):
            clip_name = clip_name[:-1] 
        
        if any([clip_name.startswith('_'), clip_name.startswith(' '), clip_name.startswith('.')]):
            clip_name = clip_name[1:]
        if any([clip_name.endswith('_'), clip_name.endswith(' '), clip_name.endswith('.')]):
            clip_name = clip_name[:-1]
        if version_number == -1:
            version_number = len(self.flame.batch.batch_iterations)
            version_padding = 3
        
        version_name = self.templates.get('version_name')
        version_name = version_name.replace('{Shot}', task_entity_name)
        version_name = version_name.replace('{name}', clip_name)
        version_name = version_name.replace('{Step}', task_step)
        version_name = version_name.replace('{Sequence}', sequence_name)
        version_name = version_name.replace('{version}', '{:03d}'.format(version_number))
        version_name = version_name.replace('{version_four}', '{:04d}'.format(version_number))

        if sg.find('Version', [['entity', 'is', shot], ['code', 'is', version_name]]):
            message = 'Version '
            message += version_name
            message += ' already exists in '
            message += task_entity_name
            message += '->'
            message += task_step
            message += '. Please iterate version number or choose another name'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        # build export path

        # That's the way they do it on toolkit
        # template_data = {}
        # template_data['Shot'] = task_entity_name
        # template_data['name'] = clip_name
        # template_data['Step'] = task_step
        # template_data['Sequence'] = sequence_name
        # template_data['version'] = '{:03d}'.format(version_number)
        # export_path.format(**template_data)

        export_path = self.templates.get('flame_render')
        export_path = export_path.replace('{Shot}', task_entity_name)
        export_path = export_path.replace('{name}', clip_name)
        export_path = export_path.replace('{Step}', task_step)
        export_path = export_path.replace('{Sequence}', sequence_name)
        export_path = export_path.replace('{version}', '{:03d}'.format(version_number))
        export_path = export_path.replace('{version_four}', '{:04d}'.format(version_number))
        export_path = os.path.join(storage_root_path, project_folder_name, export_path)

        if export_path.endswith('.exr'):
            preset_dir = self.flame.PyExporter.get_presets_dir(
                    self.flame.PyExporter.PresetVisibility.Autodesk,
                    self.flame.PyExporter.PresetType.Image_Sequence
                )
            preset_path = os.path.join(preset_dir, 'OpenEXR', 'OpenEXR (16-bit fp PIZ).xml')
        elif export_path.endswith('.dpx'):
            preset_dir = self.flame.PyExporter.get_presets_dir(
                    self.flame.PyExporter.PresetVisibility.Autodesk,
                    self.flame.PyExporter.PresetType.Image_Sequence
                )
            preset_path = os.path.join(preset_dir, 'DPX', 'DPX (10-bit).xml')
        else:
            preset_dir = self.flame.PyExporter.get_presets_dir(
                    self.flame.PyExporter.PresetVisibility.Autodesk,
                    self.flame.PyExporter.PresetType.Image_Sequence
                )
            preset_path = os.path.join(preset_dir, 'Jpeg', 'Jpeg (8-bit).xml')

        exporter = self.flame.PyExporter()
        exporter.foreground = True
        export_clip_name, ext = os.path.splitext(os.path.basename(export_path))
        export_clip_name = export_clip_name.replace('{frame}', '')
        if export_clip_name.endswith('.'):
            export_clip_name = export_clip_name[:-1]
        original_clip_name = clip.name.get_value()
        clip.name.set_value(export_clip_name)
        export_dir = os.path.dirname(export_path)
        
        if not os.path.isdir(export_dir):
            try:
                os.makedirs(export_dir)
            except:
                clip.name.set_value(original_clip_name)
                message = 'Can not create folder: ' + export_dir
                message += ' Can not complete publishing.'
                self.mbox.setText(message)
                self.mbox.exec_()
                return False

        try:
            exporter.export(clip, preset_path, export_dir)
            clip.name.set_value(original_clip_name)
        except:
            clip.name.set_value(original_clip_name)
            return None

        preset_dir = self.flame.PyExporter.get_presets_dir(
            self.flame.PyExporter.PresetVisibility.Shotgun,
            self.flame.PyExporter.PresetType.Movie
        )
        preset_path = os.path.join(preset_dir, 'Generate Preview.xml')
        clip.name.set_value(version_name + '_preview_' + uid)
        export_dir = '/var/tmp'
        preview_path = os.path.join(export_dir, version_name + '_preview_' + uid + '.mov')
        try:
            exporter.export(clip, preset_path, export_dir)
        except:
            pass

        preset_dir = self.flame.PyExporter.get_presets_dir(
            self.flame.PyExporter.PresetVisibility.Shotgun,
            self.flame.PyExporter.PresetType.Image_Sequence
        )
        preset_path = os.path.join(preset_dir, 'Generate Thumbnail.xml')
        clip.name.set_value(version_name + '_thumbnail_' + uid)
        export_dir = '/var/tmp'
        thumbnail_path = os.path.join(export_dir, version_name + '_thumbnail_' + uid + '.jpg')
        clip.in_mark = self.poster_frame
        clip.out_mark = self.poster_frame + 1
        exporter.export_between_marks = True
        try:
            exporter.export(clip, preset_path, export_dir)
        except:
            pass

        clip.name.set_value(original_clip_name)


        filters = [["code", "is", "Flame Render"]]
        sg_published_file_type = sg.find_one('PublishedFileType', filters=filters)
        if not sg_published_file_type:
            sg_published_file_type = sg.create("TankType", {"code": "Flame Render",
                                                                            "project": proj})

        # get published file type or create a published file type on the fly
        sg_published_file_type = sg.find_one('PublishedFileType', filters=[["code", "is", self.flame_render_type]])
        if not sg_published_file_type:
            sg_published_file_type = sg.create("PublishedFileType", {"code": self.flame_render_type})
        
        # /opt/Autodesk/presets/2020.2/shotgun/bundle_cache/app_store/tk-flame/v1.15.4/hooks/tk-multi-publish2/create_version.py
           
        version_data = dict(
            project = {'type': 'Project', 'id': self.connector.sg_linked_project_id},
            code = version_name,
            #description=item.description,
            entity = task_entity,
            sg_task = task,
            #sg_path_to_frames=path
        )
        version = sg.create('Version', version_data)
        if os.path.isfile(thumbnail_path):
            sg.upload_thumbnail('Version', version.get('id'), thumbnail_path)
        if os.path.isfile(preview_path):
            sg.upload('Version', version.get('id'), preview_path, 'sg_uploaded_movie')

        path_cache = self.templates.get('flame_render')
        path_cache = path_cache.replace('{Shot}', task_entity_name)
        path_cache = path_cache.replace('{name}', clip_name)
        path_cache = path_cache.replace('{Step}', task_step)
        path_cache = path_cache.replace('{Sequence}', sequence_name)
        path_cache = path_cache.replace('{version}', '{:03d}'.format(version_number))
        path_cache = path_cache.replace('{version_four}', '{:04d}'.format(version_number))
        path_cache = path_cache.replace('{frame}', '%08d')
        path_cache = os.path.join(project_folder_name, path_cache)

        published_file_data = dict(
            project = {'type': 'Project', 'id': self.connector.sg_linked_project_id},
            version_number = version_number,
            task = task,
            version = version,
            entity = task_entity,
            published_file_type = sg_published_file_type,
            path = {"relative_path": path_cache, "local_storage": self.connector.sg_storage_root},
            path_cache = path_cache,
            code = os.path.basename(path_cache),
            name = task_entity_name + ', ' + clip_name,
        )
        published_file = sg.create('PublishedFile', published_file_data)
        sg.upload_thumbnail('PublishedFile', published_file.get('id'), thumbnail_path)

        try:
            os.remove(thumbnail_path)
            os.remove(preview_path)
        except:
            pass

        message = 'Sucessfully published version: '
        message += version_name
        self.mbox.setText(message)
        self.mbox.exec_()

    def update_loader_list(self, entity):
        batch_name = self.flame.batch.name.get_value()
        add_list = self.prefs.get('additional menu ' + batch_name)
        add_list_ids = []
        entity_id = entity.get('id')
        for existing_entity in add_list:
            add_list_ids.append(existing_entity.get('id'))
        if entity_id in add_list_ids:
            for index, existing_entity in enumerate(add_list):
                if existing_entity.get('id') == entity_id:
                    add_list.pop(index)
        else:
            add_list.append(entity)
        self.prefs['additional menu ' + batch_name] = add_list

    def get_entities(self, user_only = True, filter_out=[]):
        sg = self.connector.sg_user.create_sg_connection()
        project_id = self.connector.sg_linked_project_id
        task_filters = [['project.Project.id', 'is', project_id]]

        if user_only:
            human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.connector.sg_user.login]],
                []
                )
            task_filters.append(['task_assignees', 'is', human_user])

        tasks = sg.find('Task',
            task_filters,
            ['entity']
        )

        entities = {}
        for task in tasks:
            if task['entity']:
                task_entity_type = task['entity']['type']
                task_entity_id = task['entity']['id']
                if task_entity_type not in entities.keys():
                    entities[task_entity_type] = []
                entities[task_entity_type].append(task_entity_id)

        found_entities = {}
        for entity_type in entities.keys():
            if entity_type in filter_out:
                continue
            filters = ['id', 'in']
            filters.extend(entities.get(entity_type))
            found_by_type = sg.find(entity_type, 
                [ filters ],
                ['code']
            )
            found_entities[entity_type] = list(found_by_type)

        return found_entities

    def build_flame_friendly_path(self, path):
        import glob
        import fnmatch

        file_names = os.listdir(os.path.dirname(path))
        if not file_names:
            return None
        frame_pattern = re.compile(r"^(.+?)([0-9#]+|[%]0\dd)$")
        root, ext = os.path.splitext(os.path.basename(path))
        match = re.search(frame_pattern, root)
        if not match:
            return None
        pattern = os.path.join("%s%s" % (re.sub(match.group(2), "*", root), ext))
        files = []
        for file_name in file_names:
            if fnmatch.fnmatch(file_name, pattern):
                files.append(os.path.join(os.path.dirname(path), file_name))
        if not files:
            return None
        file_roots = [os.path.splitext(f)[0] for f in files]
        frame_padding = len(re.search(frame_pattern, file_roots[0]).group(2))
        offset = len(match.group(1))

        # consitency check
        frames = []
        for f in file_roots:
            try:
                frame = int(os.path.basename(f)[offset:offset+frame_padding])
            except:
                continue
            frames.append(frame)
        if not frames:
            return None
        min_frame = min(frames)
        max_frame = max(frames)
        if ((max_frame + 1) - min_frame) != len(frames):
            # report what exactly are missing
            current_frame = min_frame
            for frame in frames:
                if not current_frame in frames:
                    # report logic to be placed here
                    pass
                current_frame += 1
            return None
        
        format_str = "[%%0%sd-%%0%sd]" % (
                frame_padding,
                frame_padding
            )
        
        frame_spec = format_str % (min_frame, max_frame)
        file_name = "%s%s%s" % (match.group(1), frame_spec, ext)

        return os.path.join(
                    os.path.dirname (path),
                    file_name
                    )

    def flip_assigned(self, *args, **kwargs):
        self.prefs['show_all'] = not self.prefs['show_all']
        self.rescan()

    def flip_assigned_for_entity(self,entity):
        entity_id = entity.get('id')
        if entity_id:
            self.prefs[entity_id]['show_all'] = not self.prefs[entity_id]['show_all']

    def page_fwd(self, *args, **kwargs):
        self.prefs['current_page'] += 1

    def page_bkw(self, *args, **kwargs):
        self.prefs['current_page'] = max(self.prefs['current_page'] - 1, 0)

    def refresh(self, *args, **kwargs):
        pass

    def show_bug_message(self, *args, **kwargs):
        if self.flame_bug_message:
            if not self.prefs['flame_bug_message_shown']:
                message = "WARINIG: There is a bug in Flame that messes up menu actions "
                message += "if total number of menu items in all menus is more then 164. "
                message += "If there's too many items displayed "
                message += "in ALL CUSTOM MENUS it will lead to the situation when "
                message += "you click on some menu item and it will call up something else. "
                message += "It only affects media hub items, menus in batch or timeline are fine. "
                message += "PS: This message will appear once per session. "
                message += "To turn it off change flame_bug_message to False "
                message += "at the top of python file"
                self.mbox.setText(message)
                self.mbox.exec_()
        self.prefs['flame_bug_message_shown'] = True



# --- FLAME STARTUP SEQUENCE ---
# Flame startup sequence is a bit complicated
# If the app installed in /opt/Autodesk/<user>/python
# project hooks are not called at startup. 
# One of the ways to work around it is to check 
# if we are able to import flame module straght away. 
# If it is the case - flame project is already loaded 
# and we can start out constructor. Otherwise we need 
# to wait for app_initialized hook to be called - that would 
# mean the project is finally loaded. 
# project_changed_dict hook seem to be a good place to wrap things up

# main objects:
# app_framework takes care of preferences and general stuff
# shotgunConnector is a gateway to shotgun database
# apps is a list of apps to load inside the main program

app_framework = None
shotgunConnector = None
apps = []

# register clean up logic to be called at Flame exit
def cleanup(apps, app_framework, shotgunConnector):
    if apps:
        if app_framework:
            print ('PYTHON\t: %s cleaning up' % app_framework.bundle_name)
            if DEBUG:
                print ('[DEBUG %s] unloading apps: %s' % (app_framework.bundle_name, pformat(apps)))
    while len(apps):
        app = apps.pop()
        del app
    if shotgunConnector:
        shotgunConnector.terminate_loops()
        del shotgunConnector
    if app_framework:
        app_framework.save_prefs()
        del app_framework

atexit.register(cleanup, apps, app_framework, shotgunConnector)

def load_apps(apps, app_framework, shotgunConnector):
    apps.append(flameMenuProjectconnect(app_framework, shotgunConnector))
    apps.append(flameBatchBlessing(app_framework))
    apps.append(flameMenuNewBatch(app_framework, shotgunConnector))
    apps.append(flameMenuBatchLoader(app_framework, shotgunConnector))
    apps.append(flameMenuPublisher(app_framework, shotgunConnector))
    if DEBUG:
        print ('[DEBUG %s] loaded %s' % (app_framework.bundle_name, pformat(apps)))

def project_changed_dict(info):
    global app_framework
    global shotgunConnector
    global apps
    cleanup(apps, app_framework, shotgunConnector)

def app_initialized(project_name):
    global app_framework
    global shotgunConnector
    global apps
    app_framework = flameAppFramework()
    print ('PYTHON\t: %s initializing' % app_framework.bundle_name)
    shotgunConnector = flameShotgunConnector(app_framework)
    load_apps(apps, app_framework, shotgunConnector)

try:
    import flame
    app_initialized(flame.project.current_project.name)
except:
    pass

# --- FLAME OPERATIONAL HOOKS ---
def project_saved(project_name, save_time, is_auto_save):
    global shotgunConnector
    if shotgunConnector:
        if shotgunConnector.rescan_flag:
            import flame
            flame.execute_shortcut('Rescan Python Hooks')
            shotgunConnector.rescan_flag = False
            
def get_main_menu_custom_ui_actions():
    menu = []
    flameMenuProjectconnectApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuProjectconnect':
            flameMenuProjectconnectApp = app
    if flameMenuProjectconnectApp:
        menu.append(flameMenuProjectconnectApp.build_menu())
        # flameMenuProjectconnectApp.refresh()
    return menu

def get_media_panel_custom_ui_actions():
    start = time.time()
    menu = []
    for app in apps:
        if app.__class__.__name__ == 'flameMenuNewBatch':
            app.register_query()
            menu.append(app.build_menu())
        if app.__class__.__name__ == 'flameMenuPublisher':
            menu.extend(app.build_menu())
    print('get_media_panel_custom_ui_actions menu update took %s' % (time.time() - start))
    return menu

def get_batch_custom_ui_actions():
    menu = []
    flameMenuBatchLoaderApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuBatchLoader':
            flameMenuBatchLoaderApp = app
    if flameMenuBatchLoaderApp:
        flameMenuBatchLoaderApp.refresh()
        for menuitem in flameMenuBatchLoaderApp.build_menu():
            menu.append(menuitem)
    return menu

def batch_render_begin(info, userData, *args, **kwargs):
    import flame
    flameBatchBlessingApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameBatchBlessing':
            flameBatchBlessingApp = app
    if not flameBatchBlessingApp:
        return
    
    # get uid and make sure there's no batch with the same name
    current_batch_uid = flameBatchBlessingApp.create_batch_uid()
    batch_file_name = flame.batch.name + '_' + current_batch_uid + '.batch'
    while os.path.isfile(batch_file_name):
        current_batch_uid = flameBatchBlessingApp.create_batch_uid()
        batch_file_name = flame.batch.name + '_' + current_batch_uid + '.batch'

    # get render destinations
    render_dest = dict()
    for node in flame.batch.nodes:
        if node.type == 'Render':
            render_dest_type = node.destination.get_value()[0]
            render_dest_name = node.destination.get_value()[1]
            render_dest_names = render_dest.get(render_dest_type, None)
            if not render_dest_names:
                render_dest_names = set()
            render_dest_names.add(node.destination.get_value()[1])
            render_dest[render_dest_type] = render_dest_names

    userData['render_dest_uids'] = flameBatchBlessingApp.collect_clip_uids(render_dest)
    userData['current_batch_uid'] = current_batch_uid

def batch_render_end(info, userData, *args, **kwargs):
    import flame
    flameBatchBlessingApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameBatchBlessing':
            flameBatchBlessingApp = app
    if not flameBatchBlessingApp:
        return

    flameBatchBlessingApp.batch_setup_root_folder()
    flame_batch_path = flameBatchBlessingApp.root_folder
    current_batch_uid = userData.get('current_batch_uid')
    batch_setup_name = flame.batch.name + '_' + current_batch_uid
    path = os.path.join(flame_batch_path, batch_setup_name)
    if not info.get('aborted'):
        print ('saving batch %s.batch' % path)
        flame.batch.save_setup(path)
        userData['batch_setup_name'] = batch_setup_name
        userData['batch_setup_file'] = path + '.batch'
    else:
        userData['batch_setup_name'] = 'Render aborted by user'

    flameBatchBlessingApp.bless_batch_renders(userData)
