'''
flameMenuSG
Flame 2020 and higher
written by Andrii Toloshnyy
andriy.toloshnyy@gmail.com
'''

import os
import sys
import time
import threading
import atexit
import inspect
import re
from pprint import pprint
from pprint import pformat

import sgtk
from sgtk.platform.qt import QtGui

menu_group_name = 'Menu(SG)'
DEBUG = False
default_templates = {
# Resolved fields are:
# {Sequence},{sg_asset_type},{Asset},{Shot},{Step},{Step_code},{name},{version},{version_four},{frame},{ext}
# {name} and {version} (or {version_four}) are taken from the clip name or from Batch name and number of Batch itertations as a fallback.
# EXAMPLE: There are 9 batch iterations in batch group.
# Any of the clips named as "mycomp", "SHOT_001_mycomp", "SHOT_001_mycomp_009", "SHOT_001_mycomp_v009"
# Would give us "mycomp" as a {name} and 009 as {version}
# Version number padding are default to 3 at the moment, ### style padding is not yet implemented
# Publishing into asset will just replace {Shot} fied with asset name
'Shot': {
    'flame_render': {
        'default': 'sequences/{Sequence}/{Shot}/{Step}/publish/{Shot}_{name}_v{version}/{Shot}_{name}_v{version}.{frame}.{ext}',
        'PublishedFileType': 'Flame Render'
        },
    'flame_batch': {
        'default': 'sequences/{Sequence}/{Shot}/{Step}/publish/flame_batch/{Shot}_{name}_v{version}.batch',
        'PublishedFileType': 'Flame Batch File'                  
        },
    'version_name': {
        'default': '{Shot}_{name}_v{version}',
    },
    'fields': ['{Sequence}', '{Shot}', '{Step}', '{Step_code}', '{name}', '{version}', '{version_four}', '{frame}', '{ext}']
},
'Asset':{
    'flame_render': {
        'default': 'assets/{sg_asset_type}/{Asset}/{Step}/publish/{Asset}_{name}_v{version}/{Asset}_{name}_v{version}.{frame}.{ext}',
        'PublishedFileType': 'Flame Render'
        },
    'flame_batch': {
        'default': 'assets/{sg_asset_type}/{Asset}/{Step}/publish/flame_batch/{Asset}_{name}_v{version}.batch',
        'PublishedFileType': 'Flame Batch File'                  
        },
    'version_name': {
        'default': '{Asset}_{name}_v{version}',
    },
    'fields': ['{Sequence}', '{sg_asset_type}', '{Asset}', '{Step}', '{Step_code}', '{name}', '{version}', '{version_four}', '{frame}', '{ext}']
}}

default_flame_export_presets = {
    # {0: flame.PresetVisibility.Project, 1: flame.PresetVisibility.Shared, 2: flame.PresetVisibility.Autodesk, 3: flame.PresetVisibility.Shotgun}
    # {0: flame.PresetType.Image_Sequence, 1: flame.PresetType.Audio, 2: flame.PresetType.Movie, 3: flame.PresetType.Sequence_Publish}
    'Publish': {'PresetVisibility': 2, 'PresetType': 0, 'PresetFile': 'OpenEXR/OpenEXR (16-bit fp PIZ).xml'},
    'Preview': {'PresetVisibility': 3, 'PresetType': 2, 'PresetFile': 'Generate Preview.xml'},
    'Thumbnail': {'PresetVisibility': 3, 'PresetType': 0, 'PresetFile': 'Generate Thumbnail.xml'}
}

loader_PublishedFileType_base = {
    'include': [],
    'exclude': []
}

__version__ = 'v0.0.11'


class flameAppFramework(object):
    # flameAppFramework class takes care of preferences

    def __init__(self):
        self.name = self.__class__.__name__
        self.bundle_name = 'flameMenuSG'
        # self.prefs scope is limited to flame project and user
        self.prefs = {}
        self.prefs_user = {}
        self.prefs_global = {}
        self.debug = DEBUG
        
        try:
            import flame
            self.flame = flame
            self.flame_project_name = self.flame.project.current_project.name
            self.flame_user_name = flame.users.current_user.name
        except:
            self.flame = None
            self.flame_project_name = None
            self.flame_user_name = None
        
        import socket
        self.hostname = socket.gethostname()
        
        if sys.platform == 'darwin':
            self.prefs_folder = os.path.join(
                os.path.expanduser('~'),
                 'Library',
                 'Caches',
                 'Shotgun',
                 self.bundle_name)
        elif sys.platform.startswith('linux'):
            self.prefs_folder = os.path.join(
                os.path.expanduser('~'),
                '.shotgun',
                self.bundle_name)

        self.prefs_folder = os.path.join(
            self.prefs_folder,
            self.hostname,
        )

        self.log('[%s] waking up' % self.__class__.__name__)
        self.load_prefs()

        # menu auto-refresh defaults

        if not self.prefs_global.get('menu_auto_refresh'):
            self.prefs_global['menu_auto_refresh'] = {
                'media_panel': True,
                'batch': False,
                'main_menu': True
            }

        self.apps = []

    def log(self, message):
        if self.debug:
            print ('[DEBUG %s] %s' % (self.bundle_name, message))

    def load_prefs(self):
        import pickle
        
        prefix = self.prefs_folder + os.path.sep + self.bundle_name
        prefs_file_path = prefix + '.' + self.flame_user_name + '.' + self.flame_project_name + '.prefs'
        prefs_user_file_path = prefix + '.' + self.flame_user_name  + '.prefs'
        prefs_global_file_path = prefix + '.prefs'

        try:
            prefs_file = open(prefs_file_path, 'r')
            self.prefs = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs))
        except:
            self.log('unable to load preferences from %s' % prefs_file_path)

        try:
            prefs_file = open(prefs_user_file_path, 'r')
            self.prefs_user = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_user_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs_user))
        except:
            self.log('unable to load preferences from %s' % prefs_user_file_path)

        try:
            prefs_file = open(prefs_global_file_path, 'r')
            self.prefs_global = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_global_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs_global))

        except:
            self.log('unable to load preferences from %s' % prefs_global_file_path)

        return True

    def save_prefs(self):
        import pickle

        if not os.path.isdir(self.prefs_folder):
            try:
                os.makedirs(self.prefs_folder)
            except:
                self.log('unable to create folder %s' % prefs_folder)
                return False

        prefix = self.prefs_folder + os.path.sep + self.bundle_name
        prefs_file_path = prefix + '.' + self.flame_user_name + '.' + self.flame_project_name + '.prefs'
        prefs_user_file_path = prefix + '.' + self.flame_user_name  + '.prefs'
        prefs_global_file_path = prefix + '.prefs'

        try:
            prefs_file = open(prefs_file_path, 'w')
            pickle.dump(self.prefs, prefs_file)
            prefs_file.close()
            self.log('preferences saved to %s' % prefs_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs))
        except:
            self.log('unable to save preferences to %s' % prefs_file_path)

        try:
            prefs_file = open(prefs_user_file_path, 'w')
            pickle.dump(self.prefs_user, prefs_file)
            prefs_file.close()
            self.log('preferences saved to %s' % prefs_user_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs_user))
        except:
            self.log('unable to save preferences to %s' % prefs_user_file_path)

        try:
            prefs_file = open(prefs_global_file_path, 'w')
            pickle.dump(self.prefs_global, prefs_file)
            prefs_file.close()
            self.log('preferences saved to %s' % prefs_global_file_path)
            self.log('preferences contents:\n' + pformat(self.prefs_global))
        except:
            self.log('unable to save preferences to %s' % prefs_global_file_path)
            
        return True

    class prefs_dict(dict):
        # subclass of a dict() in order to directly link it 
        # to main framework prefs dictionaries
        # when accessed directly it will operate on a dictionary under a 'name'
        # key in master dictionary.
        # master = {}
        # p = prefs(master, 'app_name')
        # p['key'] = 'value'
        # master - {'app_name': {'key', 'value'}}
            
        def __init__(self, master, name, **kwargs):
            self.name = name
            self.master = master
            if not self.master.get(self.name):
                self.master[self.name] = {}
            self.master[self.name].__init__()

        def __getitem__(self, k):
            return self.master[self.name].__getitem__(k)
        
        def __setitem__(self, k, v):
            return self.master[self.name].__setitem__(k, v)

        def __delitem__(self, k):
            return self.master[self.name].__delitem__(k)
        
        def get(self, k, default=None):
            return self.master[self.name].get(k, default)
        
        def setdefault(self, k, default=None):
            return self.master[self.name].setdefault(k, default)

        def pop(self, k, v=object()):
            if v is object():
                return self.master[self.name].pop(k)
            return self.master[self.name].pop(k, v)
        
        def update(self, mapping=(), **kwargs):
            self.master[self.name].update(mapping, **kwargs)
        
        def __contains__(self, k):
            return self.master[self.name].__contains__(k)

        def copy(self): # don't delegate w/ super - dict.copy() -> dict :(
            return type(self)(self)
        
        def keys(self):
            return self.master[self.name].keys()

        @classmethod
        def fromkeys(cls, keys, v=None):
            return self.master[self.name].fromkeys(keys, v)
        
        def __repr__(self):
            return '{0}({1})'.format(type(self).__name__, self.master[self.name].__repr__())

        def master_keys(self):
            return self.master.keys()


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
        
        self.prefs = self.framework.prefs_dict(self.framework.prefs, self.name)
        self.prefs_user = self.framework.prefs_dict(self.framework.prefs_user, self.name)
        self.prefs_global = self.framework.prefs_dict(self.framework.prefs_global, self.name)
        self.mbox = QtGui.QMessageBox()
        
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

    def get_export_preset_fields(self, preset):
        
        self.log('Flame export preset parser')

        # parses Flame Export preset and returns a dict of a parsed values
        # of False on error.
        # Example:
        # {'type': 'image',
        #  'fileType': 'OpenEXR',
        #  'fileExt': 'exr',
        #  'framePadding': 8
        #  'startFrame': 1001
        #  'useTimecode': 0
        # }
        
        from xml.dom import minidom

        preset_fields = {}

        # Flame type to file extension map

        flame_extension_map = {
            'Alias': 'als',
            'Cineon': 'cin',
            'Dpx': 'dpx',
            'Jpeg': 'jpg',
            'Maya': 'iff',
            'OpenEXR': 'exr',
            'Pict': 'pict',
            'Pixar': 'picio',
            'Sgi': 'sgi',
            'SoftImage': 'pic',
            'Targa': 'tga',
            'Tiff': 'tif',
            'Wavefront': 'rla',
            'QuickTime': 'mov',
            'MXF': 'mxf',
            'SonyMXF': 'mxf'
        }

        preset_path = ''

        if os.path.isfile(preset.get('PresetFile', '')):
            preset_path = preset.get('PresetFile')
        else:
            path_prefix = self.flame.PyExporter.get_presets_dir(
                self.flame.PyExporter.PresetVisibility.values.get(preset.get('PresetVisibility', 2)),
                self.flame.PyExporter.PresetType.values.get(preset.get('PresetType', 0))
            )
            preset_file = preset.get('PresetFile')
            if preset_file.startswith(os.path.sep):
                preset_file = preset_file[1:]
            preset_path = os.path.join(path_prefix, preset_file)

        self.log('parsing Flame export preset: %s' % preset_path)
        
        preset_xml_doc = None
        try:
            preset_xml_doc = minidom.parse(preset_path)
        except Exception as e:
            message = 'flameMenuSG: Unable parse xml export preset file:\n%s' % e
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        preset_fields['path'] = preset_path

        preset_type = preset_xml_doc.getElementsByTagName('type')
        if len(preset_type) > 0:
            preset_fields['type'] = preset_type[0].firstChild.data

        video = preset_xml_doc.getElementsByTagName('video')
        if len(video) < 1:
            message = 'flameMenuSG: XML parser error:\nUnable to find xml video tag in:\n%s' % preset_path
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        filetype = video[0].getElementsByTagName('fileType')
        if len(filetype) < 1:
            message = 'flameMenuSG: XML parser error:\nUnable to find video::fileType tag in:\n%s' % preset_path
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        preset_fields['fileType'] = filetype[0].firstChild.data
        if preset_fields.get('fileType', '') not in flame_extension_map:
            message = 'flameMenuSG:\nUnable to find extension corresponding to fileType:\n%s' % preset_fields.get('fileType', '')
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        preset_fields['fileExt'] = flame_extension_map.get(preset_fields.get('fileType'))

        name = preset_xml_doc.getElementsByTagName('name')
        if len(name) > 0:
            framePadding = name[0].getElementsByTagName('framePadding')
            startFrame = name[0].getElementsByTagName('startFrame')
            useTimecode = name[0].getElementsByTagName('useTimecode')
            if len(framePadding) > 0:
                preset_fields['framePadding'] = int(framePadding[0].firstChild.data)
            if len(startFrame) > 0:
                preset_fields['startFrame'] = int(startFrame[0].firstChild.data)
            if len(useTimecode) > 0:
                preset_fields['useTimecode'] = useTimecode[0].firstChild.data

        return preset_fields


class flameShotgunConnector(object):
    def __init__(self, framework):
        self.name = self.__class__.__name__
        self.framework = framework
        self.connector = self
        self.log('waking up')

        self.prefs = self.framework.prefs_dict(self.framework.prefs, self.name)
        self.prefs_user = self.framework.prefs_dict(self.framework.prefs_user, self.name)
        self.prefs_global = self.framework.prefs_dict(self.framework.prefs_global, self.name)

        # defautl values are set here
        if not 'user signed out' in self.prefs_global.keys():
            self.prefs_global['user signed out'] = False
        if not 'tank_name_overrides' in self.prefs.keys():
            # tank_name_overrides are {'project_id': 'overrided_tank_name'}
            self.prefs['tank_name_overrides'] = {}
        
        self.sg_user = None
        self.sg_human_user = None
        self.sg_user_name = None
        self.sg = None
        if not self.prefs_global.get('user signed out', False):
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
        self.loops.append(threading.Thread(target=self.sg_cache_loop, args=(45, )))
        # self.loops.append(threading.Thread(target=self.batch_group_check, args=(4, )))
        
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
        if timeout <= time_passed:
            return
        else:
            for n in range((timeout - time_passed) * 10):
                if not self.threads:
                    self.log('leaving loop thread: %s' % inspect.currentframe().f_back.f_code.co_name)
                    break
                time.sleep(0.1)

    # async cache related methods

    def async_cache_register(self, query, perform_query = True):
        import uuid

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
        if not uid:
            return False            
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
            query_body = query.get('query')
            entity = query_body.get('entity')
            filters = query_body.get('filters')
            fields = query_body.get('fields')
            self.log('async cache query: entity: %s, filters %s, fields %s' % (entity, filters, fields))
            self.async_cache[uid]['result'] = self.sg.find(entity, filters, fields)
        
        query = self.async_cache.get(uid)
        if query_type == 'result':
            return list(query.get('result'))
        
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
                        while not self.sg:
                            time.sleep(1)
                        
                        try:
                            sg = self.sg_user.create_sg_connection()
                            result = sg.find(entity, filters, fields)
                            del sg
                            self.async_cache[cache_request_uid]['result'] = result
                            results_by_hash[hash(pformat(query))] = result
                        except:
                            pass

                self.async_cache_state_check()

                self.log('sg_cache_loop took %s sec' % str(time.time() - start))
                time_passed = int(time.time() - start)
                if timeout > time_passed:
                    self.log('sg_cache_loop sleeping for %s sec' % (timeout - time_passed))
                
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
            self.prefs_global['user signed out'] = True
            return None

        if self.sg_user.are_credentials_expired():
            authenticator.clear_default_user()
            self.sg_user = authenticator.get_user()
        
        self.prefs_global['user signed out'] = False
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

    def get_pipeline_configurations(self):
        if not self.sg_user:
            return []
        if not self.sg_linked_project_id:
            return []

        pipeline_configurations = self.sg.find(
            'PipelineConfiguration', 
            [['project', 'is', {'type': 'Project', 'id': self.sg_linked_project_id}]], 
            []
            )
        return pipeline_configurations

    def get_tank_name(self, strict = False, custom=True):

        # if strict set to False:
        # returns user - overrided tank_name if exists, then
        # returns tank_name field of a project if exists, then
        # returns sanitized project name
        # if strict set to True returns tank_name field of a project or none
        # falls back to 'unknown_project" on other errors

        if not self.sg_user:
            return 'unknown_project'
        if not self.sg_linked_project_id:
            return 'unknown_project'

        if custom and self.prefs.get('tank_name_overrides'):
            if self.sg_linked_project_id in self.prefs.get('tank_name_overrides').keys():
                return (self.prefs.get('tank_name_overrides').get(self.sg_linked_project_id))

        project = self.sg.find_one(
            'Project', 
            [['id', 'is', self.sg_linked_project_id]], 
            ['name', 'tank_name']
            )
        if not project:
            return 'unknown_project'
        if strict:
            return project.get('tank_name', '')
        else:
            if not project.get('tank_name'):
                name = project.get('name')
                if not name:
                    return 'unknown_project'
                return self.sanitize_name(name).lower()

        return project.get('tank_name').lower()

    def update_tank_name(self, tank_name):
        if not self.sg_user:
            return False
        if not self.sg_linked_project_id:
            return False
        try:
            return self.sg.update('Project', self.sg_linked_project_id, {'tank_name': tank_name})
        except:
            return False

    def sanitize_name(self, name):
        if name is None:
            return None
        
        name = name.strip()
        exp = re.compile(u'[^\w\.-]', re.UNICODE)

        if isinstance(name, unicode):
            result = exp.sub('_', value)
        else:
            decoded = name.decode('utf-8')
            result = exp.sub('_', decoded).encode('utf-8')

        return re.sub('_\_+', '_', result)

    # shotgun storage root related methods

    @property
    def sg_storage_root(self):
        return self.prefs.get('sg_storage_root', {})
    @sg_storage_root.setter
    def sg_storage_root(self, value):
        self.prefs['sg_storage_root'] = value

    def resolve_project_path(self):

        # returns resoved project location on a file system
        # or empty string if project location can not be resolved

        # project can not be resolved without shotgun connection
        # and without shotgun project linked to flame

        if (not self.connector.sg_user) or (not self.connector.sg_linked_project_id):
            return ''
        
        # check if we have any storage roots defined in shotgun
        
        sg_storage_data = self.get_sg_storage_roots()

        if not sg_storage_data:
            message = '<p align = "center">'
            message += 'No Local File Storage(s) defined in Shotgun.<br><br>'
            message += '<i>(Click on arrow at the upper right corner of your Shotgun website ' 
            message += 'next to user icon and choose Site Preferences -> File Management to create one)</i><br>'
            self.mbox.setText(message)
            self.mbox.exec_()
            return ''

        # check if we have storage root already set by user
        
        if not self.sg_storage_root:

            # if there's only one storage root defined - use it
            
            if len(sg_storage_data) == 1:
                self.sg_storage_root = sg_storage_data[0]
            else:
                self.project_path_dialog()
            
            # fail if storage root has not been set in a dialog
            
            if not self.sg_storage_root:
                return ''

        tank_name = self.get_tank_name()

        return os.path.join(
            self.resolve_storage_root_path(self.sg_storage_root),
            tank_name)
        
    def project_path_dialog(self):
        from PySide2 import QtWidgets, QtCore
        window = None
        storage_root_paths = None
        sg_storage_data = self.get_sg_storage_roots()

        self.sg_storage_index = 0
        if self.sg_storage_root:
            x = 0
            for storage in sg_storage_data:
                if storage.get('id') == self.sg_storage_root.get('id'):
                    self.sg_storage_index = x
                    break
                x += 1

        self.txt_tankName = self.connector.get_tank_name(custom = False)
        self.txt_tankName_text = self.connector.get_tank_name()
        self.btn_UseCustomState = False
        
        # set 'Use Custom' button to pressed if there's tank_name override in prefs

        if self.prefs.get('tank_name_overrides'):
            if self.sg_linked_project_id in self.prefs.get('tank_name_overrides').keys():
                self.btn_UseCustomState = True

        if not sg_storage_data:
            message = '<p align = "center">'
            message += 'No Local File Storage(s) defined in Shotgun.<br><br>'
            message += '<i>(Click on arrow at the upper right corner of your Shotgun website ' 
            message += 'next to user icon and choose Site Preferences -> File Management to create one)</i><br>'
            mbox = QtGui.QMessageBox()
            mbox.setText(message)
            mbox.exec_()
            return False
        
        if not self.connector.sg_linked_project_id:
            message = 'Please link Flame project to Shotgun first'
            mbox = QtGui.QMessageBox()
            mbox.setText(message)
            mbox.exec_()
            return False

        def calculate_project_path():
            linux_path = str(sg_storage_data[self.sg_storage_index].get('linux_path'))
            mac_path = str(sg_storage_data[self.sg_storage_index].get('mac_path'))
            win_path = str(sg_storage_data[self.sg_storage_index].get('windows_path'))
            msg = 'Linux path: '
            if self.btn_UseCustomState:
                tankName = self.txt_tankName_text
            else:
                tankName = self.txt_tankName

            if linux_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(linux_path, tankName)
            else:
                msg += 'None'
            msg += '\nMac path: '
            if mac_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(mac_path, tankName)
            else:
                msg += 'None'
            msg += '\nWindows path: '
            if win_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(mac_path, tankName)
            else:
                msg += 'None'

            return msg

        def action_UseCustom():
            self.btn_UseCustomState = not self.btn_UseCustomState
            calculate_project_path()
            storage_root_paths.setText(calculate_project_path())

            if self.btn_UseCustomState:
                btn_UseCustom.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                lbl_tankName.setVisible(False)
                txt_tankName.setVisible(True)
            else:
                btn_UseCustom.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                txt_tankName.setVisible(False)
                lbl_tankName.setVisible(True)

        def combobox_changed(index):
            self.sg_storage_index = index
            storage_root_paths.setText(calculate_project_path())

        def txt_tankName_textChanged():
            self.txt_tankName_text = txt_tankName.text()
            storage_root_paths.setText(calculate_project_path())

        window = QtWidgets.QDialog()
        window.setMinimumSize(450, 180)
        window.setWindowTitle('Set Project Location')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)
        
        vbox1 = QtWidgets.QVBoxLayout()
        
        # Storage Roots Label

        lbl_sgLocalFileStorage = QtWidgets.QLabel('Shotgun Local File Storage', window)
        lbl_sgLocalFileStorage.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_sgLocalFileStorage.setMinimumHeight(28)
        lbl_sgLocalFileStorage.setMaximumHeight(28)
        lbl_sgLocalFileStorage.setAlignment(QtCore.Qt.AlignCenter)
        vbox1.addWidget(lbl_sgLocalFileStorage)

        storage_list = QtWidgets.QComboBox(window)
        for storage in sg_storage_data:
            storage_list.addItem(storage.get('code'))
        
        storage_list.setMinimumHeight(28)
        # storage_list.setStyleSheet('QComboBox {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
        #                            'QComboBox::down-arrow {image: url(/opt/Autodesk/lib64/2020.2/qml/QtQuick/Controls/Styles/Base/images/arrow-down.png); border: 0px;}'
        #                            'QComboBox::drop-down {border: 0px;}'')
        storage_list.setCurrentIndex(self.sg_storage_index)
        storage_list.currentIndexChanged.connect(combobox_changed)
        vbox1.addWidget(storage_list)

        lbl_sgProjectFolder = QtWidgets.QLabel('Project Folder Name', window)
        lbl_sgProjectFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_sgProjectFolder.setMinimumHeight(28)
        lbl_sgProjectFolder.setMaximumHeight(28)
        lbl_sgProjectFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox1.addWidget(lbl_sgProjectFolder)

        # Button and Label/Text widget switch
        wgt_tankName = QtWidgets.QWidget(window)
        wgt_tankName.setMinimumHeight(28)

        btn_UseCustom = QtWidgets.QPushButton('Use Custom', wgt_tankName)
        btn_UseCustom.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_UseCustom.setFixedSize(120, 28)
        btn_UseCustom.pressed.connect(action_UseCustom)

        lbl_tankName = QtWidgets.QLabel(self.txt_tankName, wgt_tankName)
        lbl_tankName.setFocusPolicy(QtCore.Qt.NoFocus)
        lbl_tankName.setMinimumSize(280, 28)
        lbl_tankName.move(128,0)
        lbl_tankName.setStyleSheet('QFrame {color: #9a9a9a; background-color: #222222}')
        lbl_tankName.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        lbl_tankName.setVisible(False)
        
        txt_tankName = QtWidgets.QLineEdit(self.txt_tankName_text, wgt_tankName)
        txt_tankName.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_tankName.setMinimumSize(280, 28)
        txt_tankName.move(128,0)
        txt_tankName.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_tankName.textChanged.connect(txt_tankName_textChanged)
        txt_tankName.setVisible(False)

        if self.btn_UseCustomState:
            btn_UseCustom.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            txt_tankName.setVisible(True)
        else:
            btn_UseCustom.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            lbl_tankName.setVisible(True)

        vbox1.addWidget(wgt_tankName)

        lbl_ProjectPath = QtWidgets.QLabel('Project Path', window)
        lbl_ProjectPath.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_ProjectPath.setMinimumHeight(28)
        lbl_ProjectPath.setMaximumHeight(28)
        lbl_ProjectPath.setAlignment(QtCore.Qt.AlignCenter)
        vbox1.addWidget(lbl_ProjectPath)

        project_path_info = calculate_project_path()

        storage_root_paths = QtWidgets.QLabel(calculate_project_path(), window)
        storage_root_paths.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        storage_root_paths.setStyleSheet('QFrame {color: #9a9a9a; border: 1px solid #696969 }')
        vbox1.addWidget(storage_root_paths)

        select_btn = QtWidgets.QPushButton('Select', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(100, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(100, 28)
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
            if self.btn_UseCustomState:
                self.prefs['tank_name_overrides'][self.sg_linked_project_id] = self.txt_tankName_text
            else:
                if self.prefs['tank_name_overrides']:
                    if self.sg_linked_project_id in self.prefs.get('tank_name_overrides').keys():
                        del self.prefs['tank_name_overrides'][self.sg_linked_project_id]
            self.framework.save_prefs()
        return self.sg_storage_root

    def resolve_storage_root(self, path_cache_storage):
        local_file_storages = self.get_sg_storage_roots()
        for local_file_storage in local_file_storages:
            if local_file_storage.get('id') == path_cache_storage.get('id'):
                return self.resolve_storage_root_path(local_file_storage)
        return None

    def resolve_storage_root_path(self, path_cache_storage):
        if sys.platform == 'darwin':
            platform_path_field = 'mac_path'
        elif sys.platform.startswith('linux'):
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

    def get_sg_storage_roots(self):
        if (not self.sg_user) or (not self.sg_linked_project_id):
            return []
        return self.sg.find(
            'LocalStorage',
            [],
            ['id', 'code', 'windows_path', 'linux_path', 'mac_path']
        )

    def update_sg_storage_root(self):
        sg_storage_data = self.get_sg_storage_roots()
        for storage in sg_storage_data:
            if storage.get('id') == self.sg_storage_root.get('id'):
                self.sg_storage_root = storage
                return True

        self.sg_storage_root = {}
        return False

    def batch_group_check(self, timeout):
        import flame
        self.batch_name = ''
        while self.threads:
            start = time.time()
            current_batch_name = flame.batch.name.get_value()
            if current_batch_name != self.batch_name:
                self.rescan_flag = True
            self.loop_timeout(timeout, start)


class flameMenuProjectconnect(flameMenuApp):

    # flameMenuProjectconnect app takes care of the preferences dialog as well
    
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
            # menu['name'] = self.menu_group_name + ': Link `' + flame_project_name + '` to Shotgun'
            menu['name'] = self.menu_group_name + ': Link to Shotgun'

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
        self.connector.prefs_global['user signed out'] = False
        self.connector.get_user()
        self.framework.save_prefs()
        self.rescan()

    def sign_out(self, *args, **kwargs):
        self.connector.prefs_global['user signed out'] = True
        self.connector.clear_user()
        self.framework.save_prefs()
        self.rescan()

    def preferences_window(self, *args, **kwargs):

        # The first attemt to draft preferences window in one function
        # became a bit monstrous
        # Probably need to put it in subclass instead

        from PySide2 import QtWidgets, QtCore, QtGui
        
        # storage root section
        self.connector.update_sg_storage_root()


        def compose_project_path_messge(tank_name):
            self.connector.update_sg_storage_root()

            if not self.connector.sg_storage_root:
                # no storage selected
                return 'Linux path: no storage selected\nMac path: no storage selected\nWindows path: no storage selected'
            
            linux_path = str(self.connector.sg_storage_root.get('linux_path', ''))
            mac_path = str(self.connector.sg_storage_root.get('mac_path', ''))
            win_path = str(self.connector.sg_storage_root.get('windows_path', ''))
            msg = 'Linux path: '
            if linux_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(linux_path, tank_name)
            else:
                msg += 'None'
            msg += '\nMac path: '
            if mac_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(mac_path, tank_name)
            else:
                msg += 'None'
            msg += '\nWindows path: '
            if win_path != 'None':
                if self.txt_tankName_text:
                    msg += os.path.join(mac_path, tank_name)
            else:
                msg += 'None'

            return msg

        def update_project_path_info():
            tank_name = self.connector.get_tank_name() 
            storage_root_paths.setText(compose_project_path_messge(tank_name))

        def update_pipeline_config_info():
            if self.connector.get_pipeline_configurations():
                pipeline_config_info.setText('Found')
            else:
                pipeline_config_info.setText('Clear')

        def change_storage_root_dialog():
            self.connector.project_path_dialog()

            update_pipeline_config_info()
            update_project_path_info()

        def set_presetTypeImage():
            btn_presetType.setText('File Sequence')
            self.presetType = 0
        
        def set_presetTypeMovie():
            btn_presetType.setText('Movie')
            self.presetType = 2

        def set_presetLocationProject():
            btn_PresetLocation.setText('Project')
            self.PresetVisibility = 0
            
        def set_presetLocationShared():
            btn_PresetLocation.setText('Shared')
            self.PresetVisibility = 1

        def set_presetLocationADSK():
            btn_PresetLocation.setText('Autodesk')
            self.PresetVisibility = 2

        def set_presetLocationCustom():
            btn_PresetLocation.setText('Custom')
            self.PresetVisibility = -1            

        def format_preset_details(export_preset_fields):
            preset_path = export_preset_fields.get('path')
            preset_details = ''
            preset_details += 'Name: ' + os.path.basename(preset_path) + '\n'
            preset_details += 'File Type: ' + export_preset_fields.get('fileType') + ', '
            preset_details += 'Extension: ' + export_preset_fields.get('fileExt') + '\n'
            preset_details += 'Frame Padding: ' + str(export_preset_fields.get('framePadding')) +', '
            if (export_preset_fields.get('useTimecode') == '1') or (export_preset_fields.get('useTimecode') == 'True'):
                preset_details += 'Use Timecode'
            else:
                preset_details += 'Start Frame: ' + str(export_preset_fields.get('startFrame'))
            return preset_details

        def changeExportPreset():
            dialog = QtWidgets.QFileDialog()
            dialog.setWindowTitle('Select Format Preset')
            dialog.setNameFilter('XML files (*.xml)')
            if self.PresetVisibility == -1:
                dialog.setDirectory(os.path.expanduser('~'))
            else:
                preset_folder = self.flame.PyExporter.get_presets_dir(self.flame.PyExporter.PresetVisibility.values.get(self.PresetVisibility),
                                        self.flame.PyExporter.PresetType.values.get(self.presetType))
                dialog.setDirectory(preset_folder)
            dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                file_full_path = str(dialog.selectedFiles()[0])
                file_full_path = file_full_path[len(preset_folder)+1:] if file_full_path.startswith(preset_folder) else file_full_path
                preset = {'PresetVisibility': self.PresetVisibility, 'PresetType': self.presetType, 'PresetFile': file_full_path}
                export_preset_fields = self.get_export_preset_fields(preset)
                if export_preset_fields:
                    self.framework.prefs['flameMenuPublisher']['flame_export_presets']['Publish'] = preset
                    lbl_presetDetails.setText(format_preset_details(export_preset_fields))
                else:
                    pass
        
        # Prefs window functions

        def pressGeneral():
            btn_General.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            btn_Publish.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Superclips.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            
            paneGeneral.setVisible(False)
            panePublish.setVisible(False)
            paneTemplatesSelector.setVisible(False)
            paneSuperclips.setVisible(False)

            paneGeneral.setVisible(True)

        def pressPublish():
            btn_General.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Publish.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            btn_Superclips.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')

            paneGeneral.setVisible(False)
            panePublish.setVisible(False)
            paneTemplatesSelector.setVisible(False)
            paneSuperclips.setVisible(False)

            paneTemplatesSelector.setVisible(True)
            panePublish.setVisible(True)

        def pressSuperclips():
            btn_General.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Publish.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Superclips.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')

            paneGeneral.setVisible(False)
            panePublish.setVisible(False)
            paneTemplatesSelector.setVisible(False)
            paneSuperclips.setVisible(False)

            paneSuperclips.setVisible(True)



        window = None
        window = QtWidgets.QDialog()
        window.setFixedSize(1028, 328)
        window.setWindowTitle(self.framework.bundle_name + ' Preferences')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #2e2e2e')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-400, (screen_res.height() / 2)-180)

        # Prefs Pane widgets
        
        paneTabs = QtWidgets.QWidget(window)
        paneGeneral = QtWidgets.QWidget(window)
        panePublish = QtWidgets.QWidget(window)
        paneSuperclips = QtWidgets.QWidget(window)

        # Main window HBox

        hbox_main = QtWidgets.QHBoxLayout()
        hbox_main.setAlignment(QtCore.Qt.AlignLeft)

        # Modules: apps selector preferences block
        # Modules: apps are hardcoded at the moment

        # Modules: Button functions

        vbox_apps = QtWidgets.QVBoxLayout()
        vbox_apps.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # Modules: Label

        lbl_modules = QtWidgets.QLabel('Modules', window)
        lbl_modules.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_modules.setMinimumSize(128, 28)
        lbl_modules.setAlignment(QtCore.Qt.AlignCenter)
        lbl_modules.setVisible(False)
        # vbox_apps.addWidget(lbl_modules)

        # Modules: Selection buttons

        # Modules: General preferences button

        hbox_General = QtWidgets.QHBoxLayout()
        hbox_General.setAlignment(QtCore.Qt.AlignLeft)
        btn_General = QtWidgets.QPushButton('General', window)
        btn_General.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_General.setMinimumSize(128, 28)
        btn_General.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_General.pressed.connect(pressGeneral)
        hbox_General.addWidget(btn_General)
        vbox_apps.addLayout(hbox_General, alignment = QtCore.Qt.AlignLeft)

        # Modules: flameMenuPublisher button

        hbox_Publish = QtWidgets.QHBoxLayout()
        hbox_Publish.setAlignment(QtCore.Qt.AlignLeft)
        btn_Publish = QtWidgets.QPushButton('Menu Publish', window)
        btn_Publish.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_Publish.setMinimumSize(128, 28)
        btn_Publish.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_Publish.pressed.connect(pressPublish)
        hbox_Publish.addWidget(btn_Publish)
        vbox_apps.addLayout(hbox_Publish, alignment = QtCore.Qt.AlignLeft)

        # Modules: flameSuperclips button

        hbox_Superclips = QtWidgets.QHBoxLayout()
        hbox_Superclips.setAlignment(QtCore.Qt.AlignLeft)
        btn_Superclips = QtWidgets.QPushButton('Superclips', window)
        btn_Superclips.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_Superclips.setMinimumSize(128, 28)
        btn_Superclips.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_Superclips.pressed.connect(pressSuperclips)
        hbox_Superclips.addWidget(btn_Superclips)
        vbox_apps.addLayout(hbox_Superclips, alignment = QtCore.Qt.AlignLeft)

        # Modules: End of Modules section
        hbox_main.addLayout(vbox_apps)

        # Vertical separation line
        
        vertical_sep_01 = QtWidgets.QLabel('', window)
        vertical_sep_01.setFrameStyle(QtWidgets.QFrame.VLine | QtWidgets.QFrame.Plain)
        vertical_sep_01.setStyleSheet('QFrame {color: #444444}')
        hbox_main.addWidget(vertical_sep_01)
        paneTabs.setLayout(hbox_main)
        paneTabs.move(10, 10)

        # General

        paneGeneral.setFixedSize(840, 264)
        paneGeneral.move(172, 20)
        paneGeneral.setVisible(False)

        # General::BatchLink label

        lbl_batchLink = QtWidgets.QLabel('Batch Link Autosave Path', paneGeneral)
        lbl_batchLink.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_batchLink.setMinimumSize(840, 28)
        lbl_batchLink.setAlignment(QtCore.Qt.AlignCenter)

        def update_batchLinkPathLabel():
            batch_link_path = self.framework.prefs.get('flameBatchBlessing', {}).get('flame_batch_root')
            flame_project_name = self.flame.project.current_project.name
            if self.framework.prefs['flameBatchBlessing'].get('use_project', True):
                lbl_batchLinkPath.setText(os.path.join(batch_link_path, flame_project_name))
            else:
                lbl_batchLinkPath.setText(batch_link_path)

        # General::BatchLink Enable button
        
        def enableBatchLink():
            if self.framework.prefs['flameBatchBlessing'].get('enabled', True):
                btn_batchLink.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                self.framework.prefs['flameBatchBlessing']['enabled'] = False
            else:
                btn_batchLink.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                self.framework.prefs['flameBatchBlessing']['enabled'] = True

        btn_batchLink = QtWidgets.QPushButton('Batch Link', paneGeneral)
        btn_batchLink.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_batchLink.setMinimumSize(88, 28)
        btn_batchLink.move(0, 34)
        if self.framework.prefs['flameBatchBlessing'].get('enabled', True):
            btn_batchLink.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
        else:
            btn_batchLink.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_batchLink.pressed.connect(enableBatchLink)

        # General::BatchLink default path button

        def batchLinkDefault():
            self.framework.prefs['flameBatchBlessing']['flame_batch_root'] = '/var/tmp/flameMenuSG/flame_batch_setups'
            update_batchLinkPathLabel()
        btn_batchLinkDefault = QtWidgets.QPushButton('Default', paneGeneral)
        btn_batchLinkDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_batchLinkDefault.setMinimumSize(88, 28)
        btn_batchLinkDefault.move(94, 34)
        btn_batchLinkDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_batchLinkDefault.clicked.connect(batchLinkDefault)

        # General::BatchLink path field

        lbl_batchLinkPath = QtWidgets.QLabel(paneGeneral)
        lbl_batchLinkPath.setFocusPolicy(QtCore.Qt.NoFocus)
        lbl_batchLinkPath.setMinimumSize(464, 28)
        lbl_batchLinkPath.move(188,34)
        lbl_batchLinkPath.setStyleSheet('QFrame {color: #9a9a9a; background-color: #222222}')
        lbl_batchLinkPath.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        update_batchLinkPathLabel()

        # General::BatchLink Add Flame project name button
        
        def batchLinkUseProject():            
            if self.framework.prefs['flameBatchBlessing'].get('use_project', True):
                btn_batchLinkUseProject.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                self.framework.prefs['flameBatchBlessing']['use_project'] = False
            else:
                btn_batchLinkUseProject.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                self.framework.prefs['flameBatchBlessing']['use_project'] = True
            update_batchLinkPathLabel()
        
        btn_batchLinkUseProject = QtWidgets.QPushButton('Use Project', paneGeneral)
        btn_batchLinkUseProject.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_batchLinkUseProject.setMinimumSize(88, 28)
        btn_batchLinkUseProject.move(658, 34)
        if self.framework.prefs['flameBatchBlessing'].get('use_project', True):
            btn_batchLinkUseProject.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
        else:
            btn_batchLinkUseProject.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_batchLinkUseProject.pressed.connect(batchLinkUseProject)


        # General::BatchLink Browse button
        def batchLinkBrowse():
            batch_link_path = self.framework.prefs.get('flameBatchBlessing', {}).get('flame_batch_root')
            dialog = QtWidgets.QFileDialog()
            dialog.setWindowTitle('Select Batch Autosave Folder')
            dialog.setDirectory(batch_link_path)
            new_path = dialog.getExistingDirectory(directory=batch_link_path,
                                                    options=dialog.ShowDirsOnly)
            if new_path:
                self.framework.prefs['flameBatchBlessing']['flame_batch_root'] = new_path
                update_batchLinkPathLabel()

        btn_batchLinkBrowse = QtWidgets.QPushButton('Browse', paneGeneral)
        btn_batchLinkBrowse.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_batchLinkBrowse.setMinimumSize(88, 28)
        btn_batchLinkBrowse.move(752, 34)
        btn_batchLinkBrowse.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_batchLinkBrowse.clicked.connect(batchLinkBrowse)

        # General::Loader PublishedFileTypes label

        '''

        lbl_PublishedFileTypes = QtWidgets.QLabel('Loader Published File Types', paneGeneral)
        lbl_PublishedFileTypes.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_PublishedFileTypes.setMinimumSize(536, 28)
        lbl_PublishedFileTypes.move(304, 68)
        lbl_PublishedFileTypes.setAlignment(QtCore.Qt.AlignCenter)

        # General::Loader PublishedFileTypes Button 1

        btn_PublishedFileType1 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType1.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType1.setText('Not Implemented')
        btn_PublishedFileType1.setMinimumSize(128, 28)
        btn_PublishedFileType1.move(304, 102)
        btn_PublishedFileType1.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType1_menu = QtWidgets.QMenu()
        btn_PublishedFileType1_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType1_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType1.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 2

        btn_PublishedFileType2 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType2.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType2.setText('Not Implemented')
        btn_PublishedFileType2.setMinimumSize(128, 28)
        btn_PublishedFileType2.move(440, 102)
        btn_PublishedFileType2.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType2_menu = QtWidgets.QMenu()
        btn_PublishedFileType2_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType2_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType2.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 3

        btn_PublishedFileType3 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType3.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType3.setText('Not Implemented')
        btn_PublishedFileType3.setMinimumSize(128, 28)
        btn_PublishedFileType3.move(576, 102)
        btn_PublishedFileType3.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType3_menu = QtWidgets.QMenu()
        btn_PublishedFileType3_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType3_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType3.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 4

        btn_PublishedFileType4 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType4.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType4.setText('Not Implemented')
        btn_PublishedFileType4.setMinimumSize(128, 28)
        btn_PublishedFileType4.move(712, 102)
        btn_PublishedFileType4.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType4_menu = QtWidgets.QMenu()
        btn_PublishedFileType4_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType4_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType4.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 5

        btn_PublishedFileType5 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType5.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType5.setText('Flame Batch File')
        btn_PublishedFileType5.setMinimumSize(128, 28)
        btn_PublishedFileType5.move(304, 136)
        btn_PublishedFileType5.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType5_menu = QtWidgets.QMenu()
        btn_PublishedFileType5_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType5_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType5.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 6

        btn_PublishedFileType6 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType6.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType6.setText('Flame Batch File')
        btn_PublishedFileType6.setMinimumSize(128, 28)
        btn_PublishedFileType6.move(440, 136)
        btn_PublishedFileType6.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType6_menu = QtWidgets.QMenu()
        btn_PublishedFileType6_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType6_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType6.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 7

        btn_PublishedFileType7 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType7.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType7.setText('Flame Batch File')
        btn_PublishedFileType7.setMinimumSize(128, 28)
        btn_PublishedFileType7.move(576, 136)
        btn_PublishedFileType7.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType7_menu = QtWidgets.QMenu()
        btn_PublishedFileType7_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType7_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType7.setMenu(btn_PublishedFileType1_menu)

        # General::Loader PublishedFileTypes Button 8

        btn_PublishedFileType8 = QtWidgets.QPushButton(paneGeneral)
        btn_PublishedFileType8.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PublishedFileType8.setText('Flame Batch File')
        btn_PublishedFileType8.setMinimumSize(128, 28)
        btn_PublishedFileType8.move(712, 136)
        btn_PublishedFileType8.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_PublishedFileType8_menu = QtWidgets.QMenu()
        btn_PublishedFileType8_menu.addAction('File Sequence', set_presetTypeImage)
        btn_PublishedFileType8_menu.addAction('Movie', set_presetTypeMovie)
        btn_PublishedFileType8.setMenu(btn_PublishedFileType1_menu)

        ''' # end of loader PublishedFileType settings

        # General::Create Default Task Template Label

        lbl_DefTaskTemplate = QtWidgets.QLabel('Default Task Template', paneGeneral)
        lbl_DefTaskTemplate.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_DefTaskTemplate.setMinimumSize(298, 28)
        lbl_DefTaskTemplate.move(0, 68)
        lbl_DefTaskTemplate.setAlignment(QtCore.Qt.AlignCenter)

        # General::Create Shot Task Template Label

        lbl_ShotTaskTemplate = QtWidgets.QLabel('Shot', paneGeneral)
        lbl_ShotTaskTemplate.setStyleSheet('QFrame {color: #989898;}')
        lbl_ShotTaskTemplate.setMinimumSize(36, 28)
        lbl_ShotTaskTemplate.move(0, 102)

        # General::Loader Shot Task Template Menu
        btn_ShotTaskTemplate = QtWidgets.QPushButton(paneGeneral)
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        shot_task_template = flameMenuNewBatch_prefs.get('shot_task_template', {})
        code = shot_task_template.get('code', 'No code')
        btn_ShotTaskTemplate.setText(code)
        shot_task_templates = self.connector.sg.find('TaskTemplate', [['entity_type', 'is', 'Shot']], ['code'])
        shot_task_templates_by_id = {x.get('id'):x for x in shot_task_templates}
        shot_task_templates_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in shot_task_templates}
        def selectShotTaskTemplate(template_id):
            template = shot_task_templates_by_id.get(template_id, {})
            code = template.get('code', 'no_code')
            btn_ShotTaskTemplate.setText(code)
            self.framework.prefs['flameMenuNewBatch']['shot_task_template'] = template
        btn_ShotTaskTemplate.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ShotTaskTemplate.setMinimumSize(258, 28)
        btn_ShotTaskTemplate.move(40, 102)
        btn_ShotTaskTemplate.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_ShotTaskTemplate_menu = QtWidgets.QMenu()
        for code_id in sorted(shot_task_templates_by_code_id.keys()):
            template = shot_task_templates_by_code_id.get(code_id, {})
            code = template.get('code', 'no_code')
            template_id = template.get('id')
            action = btn_ShotTaskTemplate_menu.addAction(code)
            action.triggered[()].connect(lambda template_id=template_id: selectShotTaskTemplate(template_id))
        btn_ShotTaskTemplate.setMenu(btn_ShotTaskTemplate_menu)

        # General::Create Asset Task Template Label

        lbl_AssetTaskTemplate = QtWidgets.QLabel('Asset', paneGeneral)
        lbl_AssetTaskTemplate.setStyleSheet('QFrame {color: #989898;}')
        lbl_AssetTaskTemplate.setMinimumSize(36, 28)
        lbl_AssetTaskTemplate.move(0, 136)

        # General::Loader Asset Task Template Menu
        btn_AssetTaskTemplate = QtWidgets.QPushButton(paneGeneral)
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        shot_task_template = flameMenuNewBatch_prefs.get('asset_task_template', {})
        code = shot_task_template.get('code', 'No code')
        btn_AssetTaskTemplate.setText(code)
        asset_task_templates = self.connector.sg.find('TaskTemplate', [['entity_type', 'is', 'Asset']], ['code'])
        asset_task_templates_by_id = {x.get('id'):x for x in asset_task_templates}
        asset_task_templates_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in asset_task_templates}
        def selectAssetTaskTemplate(template_id):
            template = shot_task_templates_by_id.get(template_id, {})
            code = template.get('code', 'no_code')
            btn_AssetTaskTemplate.setText(code)
            self.framework.prefs['flameMenuNewBatch']['asset_task_template'] = template
        btn_AssetTaskTemplate.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_AssetTaskTemplate.setMinimumSize(258, 28)
        btn_AssetTaskTemplate.move(40, 136)
        btn_AssetTaskTemplate.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_AssetTaskTemplate_menu = QtWidgets.QMenu()
        for code_id in sorted(asset_task_templates_by_code_id.keys()):
            template = asset_task_templates_by_code_id.get(code_id, {})
            code = template.get('code', 'no_code')
            template_id = template.get('id')
            action = btn_AssetTaskTemplate_menu.addAction(code)
            action.triggered[()].connect(lambda template_id=template_id: selectAssetTaskTemplate(template_id))
        btn_AssetTaskTemplate.setMenu(btn_AssetTaskTemplate_menu)

        # General::AutoRefresh button Label

        lbl_AutoRefresh = QtWidgets.QLabel('Refresh Menu Automatically', paneGeneral)
        lbl_AutoRefresh.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_AutoRefresh.setMinimumSize(298, 28)
        lbl_AutoRefresh.move(0, 170)
        lbl_AutoRefresh.setAlignment(QtCore.Qt.AlignCenter)

        lbl_AutoRefreshMsg = QtWidgets.QLabel('This may degrade right-click menu performance', paneGeneral)
        lbl_AutoRefreshMsg.setStyleSheet('QFrame {color: #989898;}')
        lbl_AutoRefreshMsg.setMinimumSize(36, 28)
        lbl_AutoRefreshMsg.move(0, 204)

        # General::AutoRefresh Main refresh button

        def update_AutoRefreshMain():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            main_menu = menu_auto_refresh.get('main_menu', False)
            if main_menu:
                btn_AutoRefreshMain.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            else:
                btn_AutoRefreshMain.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        def clicked_AutoRefreshMain():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            menu_auto_refresh['main_menu'] = not menu_auto_refresh.get('main_menu', False)
            self.framework.prefs_global['menu_auto_refresh'] = menu_auto_refresh
            update_AutoRefreshMain()
        btn_AutoRefreshMain = QtWidgets.QPushButton('Main Menu', paneGeneral)
        btn_AutoRefreshMain.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_AutoRefreshMain.setMinimumSize(94, 28)
        btn_AutoRefreshMain.move(0, 238)
        btn_AutoRefreshMain.clicked.connect(clicked_AutoRefreshMain)
        update_AutoRefreshMain()

        # General::AutoRefresh Batch refresh button

        def update_AutoRefreshBatch():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            batch = menu_auto_refresh.get('batch', False)
            if batch:
                btn_AutoRefreshBatch.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            else:
                btn_AutoRefreshBatch.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        def clicked_AutoRefreshBatch():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            menu_auto_refresh['batch'] = not menu_auto_refresh.get('batch', False)
            self.framework.prefs_global['menu_auto_refresh'] = menu_auto_refresh
            update_AutoRefreshBatch()
        btn_AutoRefreshBatch = QtWidgets.QPushButton('Batch Menu', paneGeneral)
        btn_AutoRefreshBatch.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_AutoRefreshBatch.setMinimumSize(94, 28)
        btn_AutoRefreshBatch.move(100, 238)
        btn_AutoRefreshBatch.clicked.connect(clicked_AutoRefreshBatch)
        update_AutoRefreshBatch()

        # General::AutoRefresh Media Panel refresh button

        def update_AutoRefreshMediaPanel():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            media_panel = menu_auto_refresh.get('media_panel', False)
            if media_panel:
                btn_AutoRefreshMediaPanel.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            else:
                btn_AutoRefreshMediaPanel.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        def clicked_AutoRefreshMediaPanel():
            menu_auto_refresh = self.framework.prefs_global.get('menu_auto_refresh', {})
            menu_auto_refresh['media_panel'] = not menu_auto_refresh.get('media_panel', False)
            self.framework.prefs_global['menu_auto_refresh'] = menu_auto_refresh
            update_AutoRefreshMediaPanel()
        btn_AutoRefreshMediaPanel = QtWidgets.QPushButton('Media Panel', paneGeneral)
        btn_AutoRefreshMediaPanel.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_AutoRefreshMediaPanel.setMinimumSize(94, 28)
        btn_AutoRefreshMediaPanel.move(200, 238)
        btn_AutoRefreshMediaPanel.clicked.connect(clicked_AutoRefreshMediaPanel)
        update_AutoRefreshMediaPanel()


        #lbl_General = QtWidgets.QLabel('General', paneGeneral)
        #lbl_General.setStyleSheet('QFrame {color: #989898}')
        #lbl_General.setAlignment(QtCore.Qt.AlignCenter)
        #lbl_General.setFixedSize(840, 264)
        #lbl_General.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)

        # Publish section:
        # Publish: main VBox
        vbox_publish = QtWidgets.QVBoxLayout()
        vbox_publish.setAlignment(QtCore.Qt.AlignTop)

        # Publish: hbox for storage root and export presets
        hbox_storage_root = QtWidgets.QHBoxLayout()
        hbox_storage_root.setAlignment(QtCore.Qt.AlignLeft)

        # Publish: StorageRoot section

        vbox_storage_root = QtWidgets.QVBoxLayout()
        vbox_storage_root.setAlignment(QtCore.Qt.AlignTop)
        
        # Publish: StorageRoot: label

        lbl_storage_root = QtWidgets.QLabel('Project Location', window)
        lbl_storage_root.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_storage_root.setMinimumSize(200, 28)
        lbl_storage_root.setAlignment(QtCore.Qt.AlignCenter)

        vbox_storage_root.addWidget(lbl_storage_root)

        # Publish: StorageRoot: button and storage root name block

        hbox_storage = QtWidgets.QHBoxLayout()
        storage_root_btn = QtWidgets.QPushButton(window)
        storage_root_btn.setText('Set Project Location')
        
        storage_root_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        storage_root_btn.setMinimumSize(199, 28)
        storage_root_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        storage_root_btn.clicked.connect(change_storage_root_dialog)
        hbox_storage.addWidget(storage_root_btn, alignment = QtCore.Qt.AlignLeft)

        storage_name = QtWidgets.QLabel('Pipeline configuration:', window)
        hbox_storage.addWidget(storage_name, alignment = QtCore.Qt.AlignLeft)

        pipeline_config_info = QtWidgets.QLabel(window)
        boldFont = QtGui.QFont()
        boldFont.setBold(True)
        pipeline_config_info.setFont(boldFont)

        update_pipeline_config_info()        
        hbox_storage.addWidget(pipeline_config_info, alignment = QtCore.Qt.AlignRight)
        vbox_storage_root.addLayout(hbox_storage)

        # Publish: StorageRoot: Paths info label
        storage_root_paths = QtWidgets.QLabel(window)
        storage_root_paths.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        storage_root_paths.setStyleSheet('QFrame {color: #9a9a9a; background-color: #2a2a2a; border: 1px solid #696969 }')
        
        update_project_path_info()

        vbox_storage_root.addWidget(storage_root_paths)
        hbox_storage_root.addLayout(vbox_storage_root)

        # Publish: StorageRoot: end of section

        # Publish: ExportPresets section

        vbox_export_preset = QtWidgets.QVBoxLayout()
        vbox_export_preset.setAlignment(QtCore.Qt.AlignTop)

        # Publish: ExportPresets: label

        lbl_export_preset = QtWidgets.QLabel('Publish Format Preset', window)
        lbl_export_preset.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_export_preset.setMinimumSize(440, 28)
        lbl_export_preset.setAlignment(QtCore.Qt.AlignCenter)
        vbox_export_preset.addWidget(lbl_export_preset)

        # Publish: ExportPresets: Change, Default buttons and preset name HBox

        hbox_export_preset = QtWidgets.QHBoxLayout()
        hbox_export_preset.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Publish: ExportPresets: Preset type selector

        btn_presetType = QtWidgets.QPushButton(window)

        self.publish_preset = self.framework.prefs.get('flameMenuPublisher', {}).get('flame_export_presets', {}).get('Publish', {})
        export_preset_fields = self.get_export_preset_fields(self.publish_preset)

        if export_preset_fields.get('type', 'image') == 'movie':
            self.presetType = 2
        else:
            self.presetType = 0

        if self.presetType == 2:
            btn_presetType.setText('Movie')
        else:
            btn_presetType.setText('File Sequence')
        
        btn_presetType.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_presetType.setMinimumSize(108, 28)
        btn_presetType.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_presetType_menu = QtWidgets.QMenu()
        btn_presetType_menu.addAction('File Sequence', set_presetTypeImage)
        btn_presetType_menu.addAction('Movie', set_presetTypeMovie)
        btn_presetType.setMenu(btn_presetType_menu)
        hbox_export_preset.addWidget(btn_presetType)

        # Publish: ExportPresets: Preset location selector

        self.exportPresetDirProject = self.flame.PyExporter.get_presets_dir(self.flame.PyExporter.PresetVisibility.values.get(0),
                                        self.flame.PyExporter.PresetType.values.get(self.presetType))
        self.exportPresetDirShared = self.flame.PyExporter.get_presets_dir(self.flame.PyExporter.PresetVisibility.values.get(1),
                                        self.flame.PyExporter.PresetType.values.get(self.presetType))
        self.exportPresetDirADSK = self.flame.PyExporter.get_presets_dir(self.flame.PyExporter.PresetVisibility.values.get(2),
                                        self.flame.PyExporter.PresetType.values.get(self.presetType))

        btn_PresetLocation = QtWidgets.QPushButton(window)

        if export_preset_fields.get('path').startswith(self.exportPresetDirProject):
            self.PresetVisibility = 0
            btn_PresetLocation.setText('Project')
        elif export_preset_fields.get('path').startswith(self.exportPresetDirShared):
            self.PresetVisibility = 1
            btn_PresetLocation.setText('Shared')
        elif export_preset_fields.get('path').startswith(self.exportPresetDirADSK):
            self.PresetVisibility = 2
            btn_PresetLocation.setText('Autodesk')
        else:
            self.PresetVisibility = -1
            btn_PresetLocation.setText('Custom')

        btn_PresetLocation.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PresetLocation.setMinimumSize(108, 28)
        btn_PresetLocation.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_PresetLocation_menu = QtWidgets.QMenu()
        btn_PresetLocation_menu.addAction('Project', set_presetLocationProject)
        btn_PresetLocation_menu.addAction('Shared', set_presetLocationShared)
        btn_PresetLocation_menu.addAction('Autodesk', set_presetLocationADSK)
        btn_PresetLocation_menu.addAction('Custom', set_presetLocationCustom)

        btn_PresetLocation.setMenu(btn_PresetLocation_menu)
        hbox_export_preset.addWidget(btn_PresetLocation)

        # Publish: ExportPresets: Export preset selector
        # this saved for feauture ADSK style menu
        '''
        btn_PresetSelector = QtWidgets.QPushButton('Publish', window)
        btn_PresetSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_PresetSelector.setMinimumSize(88, 28)
        btn_PresetSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_another_menu = QtWidgets.QMenu()
        btn_another_menu.addAction('Another action')
        btn_another_menu.setTitle('Submenu')
        btn_defaultPreset_menu = QtWidgets.QMenu()
        btn_defaultPreset_menu.addAction('Publish')
        btn_defaultPreset_menu.addAction('Preview')
        btn_defaultPreset_menu.addAction('Thumbnail')
        btn_defaultPreset_menu.addMenu(btn_another_menu)
        btn_PresetSelector.setMenu(btn_defaultPreset_menu)
        hbox_export_preset.addWidget(btn_PresetSelector)
        '''

        # Publish: ExportPresets: Change button
        
        btn_changePreset = QtWidgets.QPushButton('Load', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(changeExportPreset)
        hbox_export_preset.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)
        
        # Publish: ExportPresets: End of Change, Default buttons and preset name HBox
        vbox_export_preset.addLayout(hbox_export_preset)

        # Publish: ExportPresets: Exoprt preset details
        preset_details = format_preset_details(export_preset_fields)
        lbl_presetDetails = QtWidgets.QLabel(preset_details, window)
        lbl_presetDetails.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        lbl_presetDetails.setStyleSheet('QFrame {color: #9a9a9a; background-color: #2a2a2a; border: 1px solid #696969 }')

        vbox_export_preset.addWidget(lbl_presetDetails)

        # Publish: ExportPresets: End of Export Preset section
        hbox_storage_root.addLayout(vbox_export_preset)

        # Publish: End of upper storage root and export preset section
        vbox_publish.addLayout(hbox_storage_root)
        
        ### PUBLISH::TEMPLATES ###
        # Publish::Tempates actions

        def action_showShot():
            # btn_Entity.setText('Shot')
            btn_Shot.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Asset.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            lbl_shotTemplate.setText('Shot Publish')
            lbl_batchTemplate.setText('Shot Batch')
            lbl_versionTemplate.setText('Shot Version')
            paneAssetTemplates.setVisible(False)
            paneShotTemplates.setVisible(True)

        def action_showAsset():
            # btn_Entity.setText('Asset')
            btn_Shot.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_Asset.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            lbl_shotTemplate.setText('Asset Publish')
            lbl_batchTemplate.setText('Asset Batch')
            lbl_versionTemplate.setText('Asset Version')
            paneShotTemplates.setVisible(False)
            paneAssetTemplates.setVisible(True)

        # Publish::Tempates: Shot / Asset selector

        paneTemplatesSelector = QtWidgets.QWidget(window)
        paneTemplatesSelector.setFixedSize(158, 142)
        paneTemplatesSelector.move(0, 143)

        lbl_Entity = QtWidgets.QLabel('Entity', paneTemplatesSelector)
        lbl_Entity.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Entity.setFixedSize(128, 28)
        lbl_Entity.move(20, 0)
        lbl_Entity.setAlignment(QtCore.Qt.AlignCenter)

        btn_Shot = QtWidgets.QPushButton('Shot', paneTemplatesSelector)
        btn_Shot.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_Shot.setFixedSize(128, 28)
        btn_Shot.move(20, 34)
        btn_Shot.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_Shot.pressed.connect(action_showShot)

        btn_Asset = QtWidgets.QPushButton('Asset', paneTemplatesSelector)
        btn_Asset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_Asset.setFixedSize(128, 28)
        btn_Asset.move(20, 68)
        btn_Asset.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
        btn_Asset.pressed.connect(action_showAsset)

        # Publish::Tempates pane widget

        paneTemplates = QtWidgets.QWidget(panePublish)
        paneTemplates.setFixedSize(840, 142)

        # Publish::Tempates: label

        lbl_templates = QtWidgets.QLabel('Publishing Templates', paneTemplates)
        lbl_templates.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_templates.setFixedSize(840, 28)
        lbl_templates.setAlignment(QtCore.Qt.AlignCenter)

        # Publish::Tempates: Publish Template label
        lbl_shotTemplate = QtWidgets.QLabel('Shot Publish', paneTemplates)
        lbl_shotTemplate.setFixedSize(88, 28)
        lbl_shotTemplate.move(0, 34)

        # Publish::Tempates: Batch Template label
        lbl_batchTemplate = QtWidgets.QLabel('Shot Batch', paneTemplates)
        lbl_batchTemplate.setFixedSize(88, 28)
        lbl_batchTemplate.move(0, 68)

        # Publish::Tempates: Version Template label
        lbl_versionTemplate = QtWidgets.QLabel('Shot Version', paneTemplates)
        lbl_versionTemplate.setFixedSize(88, 28)
        lbl_versionTemplate.move(0, 102)

        # Publish::Templates::ShotPane: Show and hide
        # depending on an Entity toggle
        
        paneShotTemplates = QtWidgets.QWidget(paneTemplates)
        paneShotTemplates.setFixedSize(744, 142)
        paneShotTemplates.move(96, 0)

        # Publish::Templates::ShotPane: Publish default button
        def setShotDefault():
            txt_shot.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('flame_render').get('default', ''))
        btn_shotDefault = QtWidgets.QPushButton('Default', paneShotTemplates)
        btn_shotDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotDefault.setFixedSize(88, 28)
        btn_shotDefault.move(0, 34)
        btn_shotDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotDefault.clicked.connect(setShotDefault)

        # Publish::Templates::ShotPane: Publish template text field
        
        txt_shot_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('flame_render').get('value', '')
        txt_shot = QtWidgets.QLineEdit(txt_shot_value, paneShotTemplates)
        txt_shot.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_shot.setFixedSize(556, 28)
        txt_shot.move (94, 34)
        txt_shot.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::ShotPane: Publish template fields button
        def addShotField(field):
            txt_shot.insert(field)
        shot_template_fields = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('fields', [])
        btn_shotFields = QtWidgets.QPushButton('Add Field', paneShotTemplates)
        btn_shotFields.setFixedSize(88, 28)
        btn_shotFields.move(656, 34)
        btn_shotFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotFields_menu = QtWidgets.QMenu()
        for field in shot_template_fields:
            action = btn_shotFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addShotField(field))
        btn_shotFields.setMenu(btn_shotFields_menu)

        # Publish::Templates::ShotPane: Batch template default button
        def setShotBatchDefault():
            txt_shotBatch.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('flame_batch').get('default', ''))
        btn_shotBatchDefault = QtWidgets.QPushButton('Default', paneShotTemplates)
        btn_shotBatchDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotBatchDefault.setFixedSize(88, 28)
        btn_shotBatchDefault.move(0, 68)
        btn_shotBatchDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotBatchDefault.clicked.connect(setShotBatchDefault)

        # Publish::Templates::ShotPane: Batch template text field

        txt_shotBatch_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('flame_batch').get('value', '')
        txt_shotBatch = QtWidgets.QLineEdit(txt_shotBatch_value, paneShotTemplates)
        txt_shotBatch.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_shotBatch.setMinimumSize(556, 28)
        txt_shotBatch.move(94, 68)
        txt_shotBatch.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::ShotPane: Batch template fields button
        def addShotBatchField(field):
            txt_shotBatch.insert(field)
        btn_shotBatchFields = QtWidgets.QPushButton('Add Field', paneShotTemplates)
        btn_shotBatchFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotBatchFields.setMinimumSize(88, 28)
        btn_shotBatchFields.move(656, 68)
        btn_shotBatchFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotBatchFields_menu = QtWidgets.QMenu()
        for field in shot_template_fields:
            action = btn_shotBatchFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addShotBatchField(field))
        btn_shotBatchFields.setMenu(btn_shotBatchFields_menu)

        # Publish::Templates::ShotPane: Version template default button
        def setShotVersionDefault():
            txt_shotVersion.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('version_name').get('default', ''))
        btn_shotVersionDefault = QtWidgets.QPushButton('Default', paneShotTemplates)
        btn_shotVersionDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotVersionDefault.setMinimumSize(88, 28)
        btn_shotVersionDefault.move(0, 102)
        btn_shotVersionDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotVersionDefault.clicked.connect(setShotVersionDefault)

        # Publish::Templates::ShotPane: Vesrion template text field

        txt_shotVersion_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Shot', {}).get('version_name').get('value', '')
        txt_shotVersion = QtWidgets.QLineEdit(txt_shotVersion_value, paneShotTemplates)
        txt_shotVersion.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_shotVersion.setMinimumSize(256, 28)
        txt_shotVersion.move(94, 102)
        txt_shotVersion.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::ShotPane: Version template fields button
        def addShotVersionField(field):
            txt_shotVersion.insert(field)
        btn_shotVersionFields = QtWidgets.QPushButton('Add Field', paneShotTemplates)
        btn_shotVersionFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotVersionFields.setMinimumSize(88, 28)
        btn_shotVersionFields.move(356, 102)
        btn_shotVersionFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_shotVersionFields_menu = QtWidgets.QMenu()
        for field in shot_template_fields:
            action = btn_shotVersionFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addShotVersionField(field))
        btn_shotVersionFields.setMenu(btn_shotVersionFields_menu)

        # Publish::Templates::ShotPane: Version zero button
        '''
        def update_shotVersionZero():
            publish_prefs = self.framework.prefs.get('flameMenuPublisher', {})
            version_zero = publish_prefs.get('version_zero', False)
            if version_zero:
                btn_shotVersionZero.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            else:
                btn_shotVersionZero.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')

        def clicked_shotVersionZero():
            publish_prefs = self.framework.prefs.get('flameMenuPublisher', {})
            version_zero = publish_prefs.get('version_zero', False)
            self.framework.prefs['flameMenuPublisher']['version_zero'] = not version_zero
            update_shotVersionZero()
            update_assetVersionZero()

        btn_shotVersionZero = QtWidgets.QPushButton('Start From Zero', paneShotTemplates)
        btn_shotVersionZero.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_shotVersionZero.setMinimumSize(108, 28)
        btn_shotVersionZero.move(450, 102)
        btn_shotVersionZero.clicked.connect(clicked_shotVersionZero)
        update_shotVersionZero()
        '''

        '''
        # Publish::Templates::ShotPane: Poster Frame Label

        lbl_shotPosterFrame = QtWidgets.QLabel('Thumbnail Frame', paneShotTemplates)
        lbl_shotPosterFrame.setFixedSize(108, 28)
        lbl_shotPosterFrame.move(568, 102)
        lbl_shotPosterFrame.setStyleSheet('QLabel {color: #989898}')

        # Publish::Templates::ShotPane: Poster Frame text field

        txt_shotPosterFrame = QtWidgets.QLineEdit('1', paneShotTemplates)
        txt_shotPosterFrame.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_shotPosterFrame.setFixedSize(40, 28)
        txt_shotPosterFrame.move(682, 102)
        txt_shotPosterFrame.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        '''

        # Publish::Templates::ShotPane: END OF SECTION
        # Publish::Templates::AssetPane: Show and hide
        # depending on an Entity toggle
        
        paneAssetTemplates = QtWidgets.QWidget(paneTemplates)
        paneAssetTemplates.setFixedSize(744, 142)
        paneAssetTemplates.move(96, 0)

        # Publish::Templates::AssetPane: Publish default button
        def setAssetDefault():
            txt_asset.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('flame_render').get('default', ''))
        btn_assetDefault = QtWidgets.QPushButton('Default', paneAssetTemplates)
        btn_assetDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetDefault.setFixedSize(88, 28)
        btn_assetDefault.move(0, 34)
        btn_assetDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetDefault.clicked.connect(setAssetDefault)

        # Publish::Templates::AssetPane: Publish template text field
        txt_asset_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('flame_render').get('value', '')
        txt_asset = QtWidgets.QLineEdit(txt_asset_value, paneAssetTemplates)
        txt_asset.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_asset.setFixedSize(556, 28)
        txt_asset.move (94, 34)
        txt_asset.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::AssetPane: Publish template fields button
        asset_template_fields = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('fields', [])

        def addAssetField(field):
            txt_asset.insert(field)
        btn_assetFields = QtWidgets.QPushButton('Add Field', paneAssetTemplates)
        btn_assetFields.setFixedSize(88, 28)
        btn_assetFields.move(656, 34)
        btn_assetFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetFields_menu = QtWidgets.QMenu()
        for field in asset_template_fields:
            action = btn_assetFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addAssetField(field))
        btn_assetFields.setMenu(btn_assetFields_menu)

        # Publish::Templates::AssetPane: Batch template default button
        def setAssetBatchDefault():
            txt_assetBatch.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('flame_batch').get('default', ''))
        btn_assetBatchDefault = QtWidgets.QPushButton('Default', paneAssetTemplates)
        btn_assetBatchDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetBatchDefault.setFixedSize(88, 28)
        btn_assetBatchDefault.move(0, 68)
        btn_assetBatchDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetBatchDefault.clicked.connect(setAssetBatchDefault)

        # Publish::Templates::AssetPane: Batch template text field
        txt_assetBatch_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('flame_batch').get('value', '')
        txt_assetBatch = QtWidgets.QLineEdit(txt_assetBatch_value, paneAssetTemplates)
        txt_assetBatch.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_assetBatch.setMinimumSize(556, 28)
        txt_assetBatch.move(94, 68)
        txt_assetBatch.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::AssetPane: Batch template fields button
        def addAssetBatchField(field):
            txt_assetBatch.insert(field)
        btn_assetBatchFields = QtWidgets.QPushButton('Add Field', paneAssetTemplates)
        btn_assetBatchFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetBatchFields.setMinimumSize(88, 28)
        btn_assetBatchFields.move(656, 68)
        btn_assetBatchFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetBatchFields_menu = QtWidgets.QMenu()
        for field in asset_template_fields:
            action = btn_assetBatchFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addAssetBatchField(field))
        btn_assetBatchFields.setMenu(btn_assetBatchFields_menu)

        # Publish::Templates::AssetPane: Version template default button
        def setAssetVersionDefault():
            txt_assetVersion.setText(self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('version_name').get('default', ''))
        btn_assetVersionDefault = QtWidgets.QPushButton('Default', paneAssetTemplates)
        btn_assetVersionDefault.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetVersionDefault.setMinimumSize(88, 28)
        btn_assetVersionDefault.move(0, 102)
        btn_assetVersionDefault.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetVersionDefault.clicked.connect(setAssetVersionDefault)

        # Publish::Templates::AssetPane: Vesrion template text field
        txt_assetVersion_value = self.framework.prefs.get('flameMenuPublisher', {}).get('templates', {}).get('Asset', {}).get('version_name').get('value', '')
        txt_assetVersion = QtWidgets.QLineEdit(txt_assetVersion_value, paneAssetTemplates)
        txt_assetVersion.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_assetVersion.setMinimumSize(256, 28)
        txt_assetVersion.move(94, 102)
        txt_assetVersion.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')

        # Publish::Templates::AssetPane: Version template fields button
        def addAssetVersionField(field):
            txt_assetVersion.insert(field)
        btn_assetVersionFields = QtWidgets.QPushButton('Add Field', paneAssetTemplates)
        btn_assetVersionFields.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetVersionFields.setMinimumSize(88, 28)
        btn_assetVersionFields.move(356, 102)
        btn_assetVersionFields.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_assetVersionFields_menu = QtWidgets.QMenu()
        for field in asset_template_fields:
            action = btn_assetVersionFields_menu.addAction(field)
            action.triggered[()].connect(lambda field=field: addAssetVersionField(field))
        btn_assetVersionFields.setMenu(btn_assetVersionFields_menu)

        # Publish::Templates::AssetPane: Version zero button
        '''
        def update_assetVersionZero():
            publish_prefs = self.framework.prefs.get('flameMenuPublisher', {})
            version_zero = publish_prefs.get('version_zero', False)
            if version_zero:
                btn_assetVersionZero.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            else:
                btn_assetVersionZero.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')

        def clicked_assetVersionZero():
            publish_prefs = self.framework.prefs.get('flameMenuPublisher', {})
            version_zero = publish_prefs.get('version_zero', False)
            self.framework.prefs['flameMenuPublisher']['version_zero'] = not version_zero
            update_shotVersionZero()
            update_assetVersionZero()

        btn_assetVersionZero = QtWidgets.QPushButton('Start From Zero', paneAssetTemplates)
        btn_assetVersionZero.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_assetVersionZero.setMinimumSize(108, 28)
        btn_assetVersionZero.move(450, 102)
        btn_assetVersionZero.clicked.connect(clicked_shotVersionZero)
        update_assetVersionZero()
        '''

        # Publish::Templates::AssetPane: END OF SECTION


        vbox_publish.addWidget(paneTemplates)
        panePublish.setLayout(vbox_publish)
        panePublish.setFixedSize(860, 280)
        panePublish.move(160, 10)
        panePublish.setVisible(False)


        # Superclips

        paneSuperclips.setFixedSize(840, 264)
        paneSuperclips.move(172, 20)
        paneSuperclips.setVisible(False)
        lbl_paneSuperclips = QtWidgets.QLabel('Superclis', paneSuperclips)
        lbl_paneSuperclips.setStyleSheet('QFrame {color: #989898}')
        lbl_paneSuperclips.setFixedSize(840, 264)
        lbl_paneSuperclips.setAlignment(QtCore.Qt.AlignCenter)
        lbl_paneSuperclips.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)

        # Close button

        def close_prefs_dialog():
            self.framework.prefs['flameMenuPublisher']['templates']['Shot']['flame_render']['value'] = txt_shot.text().encode('utf-8')
            self.framework.prefs['flameMenuPublisher']['templates']['Shot']['flame_batch']['value'] = txt_shotBatch.text().encode('utf-8')
            self.framework.prefs['flameMenuPublisher']['templates']['Shot']['version_name']['value'] = txt_shotVersion.text().encode('utf-8')
            self.framework.save_prefs()
            window.accept()

        close_btn = QtWidgets.QPushButton('Close', window)
        close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        close_btn.setFixedSize(88, 28)
        close_btn.move(924, 292)
        close_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        close_btn.clicked.connect(close_prefs_dialog)

        # Set default tab and start window

        action_showShot()
        pressPublish()
        window.exec_()

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        self.connector.async_cache_get(self.active_projects_uid, True)

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log('Rescan Python Hooks')
            if self.connector:
                self.connector.rescan_flag = False


class flameBatchBlessing(flameMenuApp):
    def __init__(self, framework):
        flameMenuApp.__init__(self, framework)
        
        # app defaults
        if not self.prefs:
            self.prefs['flame_batch_root'] = '/var/tmp/flameMenuSG/flame_batch_setups'
            self.prefs['enabled'] = True
            self.prefs['use_project'] = True

        self.root_folder = self.batch_setup_root_folder()

    def batch_setup_root_folder(self):
        try:
            import flame
        except:
            return False

        flame_batch_name = flame.batch.name.get_value()
        current_project_name = flame.project.current_project.name

        if self.prefs.get('use_project'):
            flame_batch_path = os.path.join(
                                        self.prefs.get('flame_batch_root'),
                                        current_project_name,
                                        flame_batch_name)
        else:
            flame_batch_path = os.path.join(
                                        self.prefs.get('flame_batch_root'),
                                        flame_batch_name)
        
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
        import uuid
        from datetime import datetime
        
        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
        timestamp = (datetime.now()).strftime('%Y%b%d_%H%M').upper()
        return timestamp + '_' + uid[:3]


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

        if not self.prefs.master.get(self.name):
            self.prefs['show_all'] = True
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 128

            self.prefs['last_sequence_used'] = {}

            task_templates = self.connector.sg.find('TaskTemplate', [], ['entity_type','code'])
            task_templates_by_id = {x.get('id'):x for x in task_templates}

            if 42 in task_templates_by_id.keys():
                self.prefs['shot_task_template'] = task_templates_by_id.get(42)
            else:

                # set to first id avaliable for Shot

                for template_id in sorted(task_templates_by_id.keys()):
                    template = task_templates_by_id.get(template_id, {})
                    if template.get('entity_type') == 'Shot':
                        self.prefs['shot_task_template'] = template
                        break
            if 41 in task_templates_by_id.keys():
                self.prefs['asset_task_template'] = task_templates_by_id.get(41)
            else:

                # set to first id avaliable for Asset

                for template_id in sorted(task_templates_by_id.keys()):
                    template = task_templates_by_id.get(template_id, {})
                    if template.get('entity_type') == 'Asset':
                        self.prefs['asset_task_template'] = template
                        break

    def __getattr__(self, name):
        def method(*args, **kwargs):
            entity = self.dynamic_menu_data.get(name)
            if entity:
                self.create_new_batch(entity)
        return method

    def build_menu(self):
        '''
        # ---------------------------------
        # menu build time debug code

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
        # menu build time debug code
        '''

        if not self.connector.sg_user:
            return []
        if not self.connector.sg_linked_project_id:
            return []
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

        # found entities menu

        user_only = not self.prefs['show_all']
        filter_out = ['Project', 'Sequence']
        found_entities = self.get_entities(user_only, filter_out)
        menu_main_body = []

        if not found_entities:
            menu_item = {}
            menu_item['name'] = '- [ Assets ] [+]'
            menu_item['execute'] = self.create_asset_dialog
            menu_item['waitCursor'] = False
            menu_main_body.append(menu_item)

            menu_item = {}
            menu_item['name'] = '- [ Shots ] [+]'
            menu_item['execute'] = self.create_shot_dialog
            menu_item['waitCursor'] = False
            menu_main_body.append(menu_item)
        
        if len(found_entities.keys()) == 1:
            if 'Shot' in found_entities.keys():
                menu_item = {}
                menu_item['name'] = '- [ Assets ] [+]'
                menu_item['execute'] = self.create_asset_dialog
                menu_item['waitCursor'] = False
                menu_main_body.append(menu_item)

        menu_ctrls_len = len(menu)
        menu_lenght = menu_ctrls_len
        menu_lenght += len(found_entities.keys())
        for entity_type in found_entities.keys():
            menu_lenght += len(found_entities.get(entity_type))
        max_menu_lenght = self.prefs.get('menu_max_items_per_page')

        for index, entity_type in enumerate(sorted(found_entities.keys())):

            menu_item = {}
            menu_item['name'] = '- [ ' + entity_type + 's ] [+]'
            if entity_type == 'Asset':
                menu_item['execute'] = self.create_asset_dialog
            elif entity_type == 'Shot':
                menu_item['execute'] = self.create_shot_dialog
            else:
                menu_item['execute'] = self.rescan
            menu_item['waitCursor'] = False
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

        if len(found_entities.keys()) == 1:
            if 'Asset' in found_entities.keys():
                menu_item = {}
                menu_item['name'] = '- [ Shots ] [+]'
                menu_item['execute'] = self.create_shot_dialog
                menu_item['waitCursor'] = False
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
        cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

        if not isinstance(cached_tasks, list):
            
            # try to unregister cache and register again

            self.unregister_query()
            self.register_query()

            cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

            if not isinstance(cached_tasks, list):

                # give up

                return {}

        if not cached_tasks:
            return {}

        tasks = []
        if user_only:
            for task in cached_tasks:
                task_assignees = task.get('task_assignees')
                for task_assignee in task_assignees:
                    if task_assignee.get('id') == self.connector.sg_human_user.get('id'):
                        tasks.append(task)
        else:
            tasks = list(cached_tasks)

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
        sg = self.connector.sg

        # check if flame batch with entity name already in desktop

        entity = sg.find_one (
            entity.get('type'),
            [['id', 'is', entity.get('id')]],
            ['code', 'sg_head_in', 'sg_tail_out', 'sg_vfx_requirements']
        )

        batch_groups = []
        for batch_group in self.flame.project.current_project.current_workspace.desktop.batch_groups:
            batch_groups.append(batch_group.name.get_value())

        code = entity.get('code')
        if not code:
            code = 'New Batch'

        if code in batch_groups:
            return False

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
        
        sg_head_in = entity.get('sg_head_in')
        if not sg_head_in:
            sg_head_in = 1001
        
        sg_tail_out = entity.get('sg_tail_out')
        if not sg_tail_out:
            sg_tail_out = 1100

        sg_vfx_req = entity.get('sg_vfx_requirements')
        if not sg_vfx_req:
            sg_vfx_req = 'no requirements specified'

        dur = (sg_tail_out - sg_head_in) + 1

        self.flame.batch.create_batch_group (
            code, start_frame = 1, duration = dur
        )
        
        for flame_path in flame_paths_to_import:
            self.flame.batch.import_clip(flame_path, 'Schematic Reel 1')

        render_node = self.flame.batch.create_node('Render')
        render_node.name.set_value('<batch name>_comp_v<iteration###>')

        self.flame.batch.organize()

    def create_asset_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore

        self.asset_name = ''
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        self.asset_task_template =  flameMenuNewBatch_prefs.get('asset_task_template', {})

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Create Asset in Shotgun')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)

        # Asset Task Template label

        lbl_TaskTemplate = QtWidgets.QLabel('Task Template', window)
        lbl_TaskTemplate.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_TaskTemplate.setMinimumHeight(28)
        lbl_TaskTemplate.setMaximumHeight(28)
        lbl_TaskTemplate.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_TaskTemplate)

        # Shot Task Template Menu

        btn_AssetTaskTemplate = QtWidgets.QPushButton(window)
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        asset_task_template = flameMenuNewBatch_prefs.get('asset_task_template', {})
        code = asset_task_template.get('code', 'No code')
        btn_AssetTaskTemplate.setText(code)
        asset_task_templates = self.connector.sg.find('TaskTemplate', [['entity_type', 'is', 'Asset']], ['code'])
        asset_task_templates_by_id = {x.get('id'):x for x in asset_task_templates}
        asset_task_templates_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in asset_task_templates}
        def selectAssetTaskTemplate(template_id):
            template = shot_task_templates_by_id.get(template_id, {})
            code = template.get('code', 'no_code')
            btn_AssetTaskTemplate.setText(code)
            self.asset_task_template = template
        btn_AssetTaskTemplate.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_AssetTaskTemplate.setMinimumSize(258, 28)
        btn_AssetTaskTemplate.move(40, 102)
        btn_AssetTaskTemplate.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_AssetTaskTemplate_menu = QtWidgets.QMenu()
        for code_id in sorted(asset_task_templates_by_code_id.keys()):
            template = asset_task_templates_by_code_id.get(code_id, {})
            code = template.get('code', 'no_code')
            template_id = template.get('id')
            action = btn_AssetTaskTemplate_menu.addAction(code)
            action.triggered[()].connect(lambda template_id=template_id: selectAssetTaskTemplate(template_id))
        btn_AssetTaskTemplate.setMenu(btn_AssetTaskTemplate_menu)
        vbox.addWidget(btn_AssetTaskTemplate)

        # Shot Name Label

        lbl_AssettName = QtWidgets.QLabel('New Asset Name', window)
        lbl_AssettName.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_AssettName.setMinimumHeight(28)
        lbl_AssettName.setMaximumHeight(28)
        lbl_AssettName.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_AssettName)

        # Shot Name Text Field
        def txt_AssetName_textChanged():
            self.asset_name = txt_AssetName.text()
        txt_AssetName = QtWidgets.QLineEdit('', window)
        txt_AssetName.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_AssetName.setMinimumSize(280, 28)
        txt_AssetName.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_AssetName.textChanged.connect(txt_AssetName_textChanged)
        vbox.addWidget(txt_AssetName)

        # Spacer Label

        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_Spacer)

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            if self.asset_name == '':
                return {}
            else:
                data = {'project': {'type': 'Project','id': self.connector.sg_linked_project_id},
                'code': self.asset_name,
                'task_template': self.asset_task_template}
                self.log('creating new asset...')
                new_asset = self.connector.sg.create('Asset', data)
                self.log('new asset:\n%s' % pformat(new_asset))
                self.log('updating async cache for uid: %s' % self.current_tasks_uid)
                self.connector.async_cache_get(self.current_tasks_uid, True)
                self.log('creating new batch')
                self.create_new_batch(new_asset)

                for app in self.framework.apps:
                    app.rescan()

                return new_asset
        else:
            return {}

    def create_shot_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore

        self.sequence_name = ''
        self.sequence_id = -1
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        self.shot_task_template =  flameMenuNewBatch_prefs.get('shot_task_template', {})
        self.shot_name = ''

        def newSequenceDialog():
            window_NewSequnece = QtWidgets.QDialog()
            window_NewSequnece.setMinimumSize(280, 100)
            window_NewSequnece.setWindowTitle('Create New Sequence in Shotgun')
            window_NewSequnece.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
            window_NewSequnece.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            window_NewSequnece.setStyleSheet('background-color: #313131')

            screen_res = QtWidgets.QDesktopWidget().screenGeometry()
            window_NewSequnece.move((screen_res.width()/2)-150, (screen_res.height() / 2)-280)

            vbox_NewSequnece = QtWidgets.QVBoxLayout()
            vbox_NewSequnece.setAlignment(QtCore.Qt.AlignTop)

            # Shot Name Label

            lbl_SequenceName = QtWidgets.QLabel('New Sequence Name', window_NewSequnece)
            lbl_SequenceName.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
            lbl_SequenceName.setMinimumHeight(28)
            lbl_SequenceName.setMaximumHeight(28)
            lbl_SequenceName.setAlignment(QtCore.Qt.AlignCenter)
            vbox_NewSequnece.addWidget(lbl_SequenceName)

            # Sequence Name Text Field
            def txt_NewSequenceName_textChanged():
                self.sequence_name = txt_NewSequenceName.text()
            txt_NewSequenceName = QtWidgets.QLineEdit('', window_NewSequnece)
            txt_NewSequenceName.setFocusPolicy(QtCore.Qt.ClickFocus)
            txt_NewSequenceName.setMinimumSize(280, 28)
            txt_NewSequenceName.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
            txt_NewSequenceName.textChanged.connect(txt_NewSequenceName_textChanged)
            vbox_NewSequnece.addWidget(txt_NewSequenceName)

            # Create and Cancel Buttons
            hbox_NewSequneceCreate = QtWidgets.QHBoxLayout()

            btn_NewSequenceCreate = QtWidgets.QPushButton('Create', window_NewSequnece)
            btn_NewSequenceCreate.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_NewSequenceCreate.setMinimumSize(128, 28)
            btn_NewSequenceCreate.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
            btn_NewSequenceCreate.clicked.connect(window_NewSequnece.accept)

            btn_NewSequenceCancel = QtWidgets.QPushButton('Cancel', window_NewSequnece)
            btn_NewSequenceCancel.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_NewSequenceCancel.setMinimumSize(128, 28)
            btn_NewSequenceCancel.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
            btn_NewSequenceCancel.clicked.connect(window_NewSequnece.reject)

            hbox_NewSequneceCreate.addWidget(btn_NewSequenceCancel)
            hbox_NewSequneceCreate.addWidget(btn_NewSequenceCreate)

            vbox_NewSequnece.addLayout(hbox_NewSequneceCreate)

            window_NewSequnece.setLayout(vbox_NewSequnece)

            if window_NewSequnece.exec_():
                if self.sequence_name == '':
                    return {}
                else:
                    data = {'project': {'type': 'Project','id': self.connector.sg_linked_project_id},
                    'code': self.sequence_name}
                    return self.connector.sg.create('Sequence', data)
            else:
                return {}

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Create Shot in Shotgun')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)

        # Sequence label

        lbl_Sequence = QtWidgets.QLabel('Sequence', window)
        lbl_Sequence.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Sequence.setMinimumHeight(28)
        lbl_Sequence.setMaximumHeight(28)
        lbl_Sequence.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_Sequence)

        # Sequence Selector and New Sequence Button Hbox

        # hbox_Sequence = QtWidgets.QHBoxLayout()
        # hbox_Sequence.setAlignment(QtCore.Qt.AlignLeft)

        # Sequence Selector Button

        btn_Sequence = QtWidgets.QPushButton(window)
        self.sequences = self.connector.sg.find('Sequence', 
            [['project', 'is', {'type': 'Project', 'id': self.connector.sg_linked_project_id}]], 
            ['code'])
        if self.prefs.get('last_sequence_used'):
            sequence = self.prefs.get('last_sequence_used', {})
            code = sequence.get('code', 'No Name')
            self.sequence_id = sequence.get('id', -1)
        else:
            code = 'DefaultSequence'
        btn_Sequence.setText(code)
        self.sequences_by_id = {x.get('id'):x for x in self.sequences}
        self.sequences_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in self.sequences}
        def selectSequence(sequence_id):
            
            if sequence_id == 0:
                new_sequence = newSequenceDialog()
                if new_sequence:
                    btn_Sequence_menu.clear()
                    self.sequences = self.connector.sg.find('Sequence', 
                    [['project', 'is', {'type': 'Project', 'id': self.connector.sg_linked_project_id}]], 
                    ['code'])
                    self.sequences_by_id = {x.get('id'):x for x in self.sequences}
                    self.sequences_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in self.sequences}
                    action = btn_Sequence_menu.addAction('DefaultSequence')
                    action.triggered[()].connect(lambda sequence_id=-1: selectSequence(sequence_id))
                    for code_id in sorted(self.sequences_by_code_id.keys()):
                        sequence = self.sequences_by_code_id.get(code_id, {})
                        code = sequence.get('code', 'No code')
                        sequence_id = sequence.get('id')
                        action = btn_Sequence_menu.addAction(code)
                        action.triggered[()].connect(lambda sequence_id=sequence_id: selectSequence(sequence_id))
                    action = btn_Sequence_menu.addAction('Create New Sequence...')
                    action.triggered[()].connect(lambda sequence_id=0: selectSequence(sequence_id))
                    btn_Sequence.setMenu(btn_Sequence_menu)
                    self.sequence_id = new_sequence.get('id')
                    btn_Sequence.setText(new_sequence.get('code'))

            elif sequence_id == -1:
                self.sequence_id = -1
                btn_Sequence.setText('DefaultSequence')
                return
            else:
                sequence = self.sequences_by_id.get(sequence_id, {})
                code = sequence.get('code', 'no_code')
                btn_Sequence.setText(code)
                self.sequence_id = sequence_id
                self.prefs['last_sequence_used'] = sequence

        btn_Sequence.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_Sequence.setMinimumSize(280, 28)
        btn_Sequence.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_Sequence_menu = QtWidgets.QMenu()
        action = btn_Sequence_menu.addAction('DefaultSequence')
        action.triggered[()].connect(lambda sequence_id=-1: selectSequence(sequence_id))
        for code_id in sorted(self.sequences_by_code_id.keys()):
            sequence = self.sequences_by_code_id.get(code_id, {})
            code = sequence.get('code', 'No code')
            sequence_id = sequence.get('id')
            action = btn_Sequence_menu.addAction(code)
            action.triggered[()].connect(lambda sequence_id=sequence_id: selectSequence(sequence_id))
        action = btn_Sequence_menu.addAction('Create New Sequence...')
        action.triggered[()].connect(lambda sequence_id=0: selectSequence(sequence_id))
        btn_Sequence.setMenu(btn_Sequence_menu)
        vbox.addWidget(btn_Sequence)

        # Shot Task Template label

        lbl_TaskTemplate = QtWidgets.QLabel('Task Template', window)
        lbl_TaskTemplate.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_TaskTemplate.setMinimumHeight(28)
        lbl_TaskTemplate.setMaximumHeight(28)
        lbl_TaskTemplate.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_TaskTemplate)

        # Shot Task Template Menu

        btn_ShotTaskTemplate = QtWidgets.QPushButton(window)
        flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        shot_task_template = flameMenuNewBatch_prefs.get('shot_task_template', {})
        code = shot_task_template.get('code', 'No code')
        btn_ShotTaskTemplate.setText(code)
        shot_task_templates = self.connector.sg.find('TaskTemplate', [['entity_type', 'is', 'Shot']], ['code'])
        shot_task_templates_by_id = {x.get('id'):x for x in shot_task_templates}
        shot_task_templates_by_code_id = {x.get('code') + '_' + str(x.get('id')):x for x in shot_task_templates}
        def selectShotTaskTemplate(template_id):
            template = shot_task_templates_by_id.get(template_id, {})
            code = template.get('code', 'no_code')
            btn_ShotTaskTemplate.setText(code)
            self.shot_task_template = template
        btn_ShotTaskTemplate.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ShotTaskTemplate.setMinimumSize(258, 28)
        btn_ShotTaskTemplate.move(40, 102)
        btn_ShotTaskTemplate.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_ShotTaskTemplate_menu = QtWidgets.QMenu()
        for code_id in sorted(shot_task_templates_by_code_id.keys()):
            template = shot_task_templates_by_code_id.get(code_id, {})
            code = template.get('code', 'no_code')
            template_id = template.get('id')
            action = btn_ShotTaskTemplate_menu.addAction(code)
            action.triggered[()].connect(lambda template_id=template_id: selectShotTaskTemplate(template_id))
        btn_ShotTaskTemplate.setMenu(btn_ShotTaskTemplate_menu)
        vbox.addWidget(btn_ShotTaskTemplate)

        # Shot Name Label

        lbl_ShotName = QtWidgets.QLabel('New Shot Name', window)
        lbl_ShotName.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_ShotName.setMinimumHeight(28)
        lbl_ShotName.setMaximumHeight(28)
        lbl_ShotName.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_ShotName)

        # Shot Name Text Field
        def txt_ShotName_textChanged():
            self.shot_name = txt_ShotName.text()
        txt_ShotName = QtWidgets.QLineEdit('', window)
        txt_ShotName.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_ShotName.setMinimumSize(280, 28)
        txt_ShotName.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_ShotName.textChanged.connect(txt_ShotName_textChanged)
        vbox.addWidget(txt_ShotName)

        # Spacer Label

        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_Spacer)

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            if self.shot_name == '':
                return {}
            else:
                if self.sequence_id == -1:
                    shot_sequence = self.connector.sg.find_one('Sequence',
                        [['project', 'is', {'type': 'Project', 'id': self.connector.sg_linked_project_id}], 
                        ['code', 'is', 'DefaultSequence']]
                        )
                    if not shot_sequence:
                        sequence_data = {'project': {'type': 'Project','id': self.connector.sg_linked_project_id},
                        'code': 'DefaultSequence'}
                        shot_sequence = self.connector.sg.create('Sequence', sequence_data)
                else:
                    shot_sequence = self.connector.sg.find_one('Sequence', [['id', 'is', self.sequence_id]])

                data = {'project': {'type': 'Project','id': self.connector.sg_linked_project_id},
                'code': self.shot_name,
                'sg_sequence': shot_sequence,
                'task_template': self.shot_task_template}
                self.log('creating new shot...')
                new_shot = self.connector.sg.create('Shot', data)
                self.log('new shot:\n%s' % pformat(new_shot))
                self.log('updating async cache for uid: %s' % self.current_tasks_uid)
                self.connector.async_cache_get(self.current_tasks_uid, True)
                self.log('creating new batch')
                self.create_new_batch(new_shot)

                for app in self.framework.apps:
                    app.rescan()

                return new_shot
        else:
            return {}

        '''
        data = {'project': {'type': 'Project','id': 4},
        'code': '100_010',
        'description': 'dark shot with wicked cool ninjas',
        'task_template': template }
        result = sg.create('Shot', data)
        '''

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
                    'fields': [
                        'content',
                        'step.Step.code',
                        'step.Step.short_name',
                        'task_assignees',
                        'project.Project.id',
                        'entity',
                        'entity.Asset.sg_asset_type',
                        'entity.Shot.sg_sequence'
                    ]
                })
                return True
            else:
                return False
            
        elif self.connector.sg_linked_project_id and not self.current_tasks_uid:
            # register new query from scratch
            self.current_tasks_uid = self.connector.async_cache_register({
                    'entity': 'Task',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': [
                        'content',
                        'step.Step.code',
                        'step.Step.short_name',
                        'task_assignees',
                        'project.Project.id',
                        'entity',
                        'entity.Asset.sg_asset_type',
                        'entity.Shot.sg_sequence'
                    ] 
            })
            return True
        elif self.current_tasks_uid and not self.connector.sg_linked_project_id:
            # unregister current uid
            self.connector.async_cache_unregister(self.current_tasks_uid)
            return True
        else:
            return False

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        self.connector.async_cache_get(self.current_tasks_uid, True)

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log('Rescan Python Hooks')
            if self.connector:
                self.connector.rescan_flag = False


class flameMenuBatchLoader(flameMenuApp):
    def __init__(self, framework, connector):
        self.types_to_include = [
            'Image Sequence',
            'Flame Render'
        ]

        flameMenuApp.__init__(self, framework)
        self.connector = connector

        # app defaults
        if not self.prefs.master.get(self.name):
            self.prefs['show_all'] = True
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 128

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
        if not self.connector.sg_linked_project_id:
            return None
        
        sg = self.connector.sg

        batch_name = self.flame.batch.name.get_value()
        if (('additional menu ' + batch_name) in self.prefs.keys()) and self.prefs.get('additional menu ' + batch_name):
            add_menu_list = self.prefs.get('additional menu ' + batch_name)
            for index, stored_entity in enumerate(add_menu_list):
                stored_entity_type = stored_entity.get('type', 'Shot')
                stored_entity_id = stored_entity.get('id', 0)
                found_entity = sg.find_one(stored_entity_type, [['id', 'is', stored_entity_id]])
                if not found_entity:
                    add_menu_list.pop(index)

            if not add_menu_list:
                project_id = self.connector.sg_linked_project_id
                tasks = sg.find('Task',
                    [['project.Project.id', 'is', project_id]],
                    ['entity']
                )
                entity = {}
                for task in tasks:
                    current_entity = task.get('entity')
                    if current_entity:
                        if current_entity.get('name') == batch_name:
                            entity = current_entity
                            break
                if entity:
                    self.update_loader_list(entity)
                add_menu_list = self.prefs.get('additional menu ' + batch_name)

        else:
            self.prefs['additional menu ' + batch_name] = []
            project_id = self.connector.sg_linked_project_id
            task_filters = [['project.Project.id', 'is', project_id]]
            tasks = sg.find('Task',
                task_filters,
                ['entity']
            )
            entity = {}
            for task in tasks:
                current_entity = task.get('entity')
                if current_entity:
                    if current_entity.get('name') == batch_name:
                        entity = current_entity
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
        sg = self.connector.sg

        entity_type = entity.get('type')
        entity_id = entity.get('id')

        found_entity = sg.find_one(
                    entity_type,
                    [['id', 'is', entity_id]],
                    ['code']
        )

        if not found_entity:
            return {}

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
        sg = self.connector.sg
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
        flameMenuApp.__init__(self, framework)
        self.connector = connector

        # app defaults
        if not self.prefs.master.get(self.name):
            self.prefs['show_all'] = True
            self.prefs['current_page'] = 0
            self.prefs['menu_max_items_per_page'] = 128
            self.prefs['flame_bug_message_shown'] = False
            self.prefs['templates'] = default_templates
            # init values from default
            for entity_type in self.prefs['templates'].keys():
                for template in self.prefs['templates'][entity_type].keys():
                    if isinstance(self.prefs['templates'][entity_type][template], dict):
                        if 'default' in self.prefs['templates'][entity_type][template].keys():
                            self.prefs['templates'][entity_type][template]['value'] = self.prefs['templates'][entity_type][template]['default']
                        
            self.prefs['flame_export_presets'] = default_flame_export_presets
            self.prefs['poster_frame'] = 1
            self.prefs['version_zero'] = False

        self.flame_bug_message = False
        self.selected_clips = []
        self.mbox = QtGui.QMessageBox()
        self.create_export_presets()
        
        # async cache related initialization
        self.current_tasks_uid = None
        self.current_versions_uid = None
        self.register_query()
        
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
        import uuid

        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
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
        tasks = []
        cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

        if not isinstance(cached_tasks, list):
            
            # try to unregister cache and register again

            self.unregister_query()
            self.register_query()

            cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

            if not isinstance(cached_tasks, list):

                # give up

                return []

        for cached_task in cached_tasks:
            if not cached_task.get('entity'):
                continue
            tasks.append(cached_task)
        entities_id_list = [task.get('entity').get('id') for task in tasks]
        
        add_menu_list = []

        if (('additional menu ' + batch_name) in self.prefs.keys()) and self.prefs.get('additional menu ' + batch_name):
            add_menu_list = self.prefs.get('additional menu ' + batch_name)

            for index, stored_entity in enumerate(add_menu_list):
                stored_entity_type = stored_entity.get('type', 'Shot')
                stored_entity_id = stored_entity.get('id', 0)
                if not stored_entity_id in entities_id_list:
                    add_menu_list.pop(index)
            
            if not add_menu_list:                                
                entity = {}
                for task in tasks:
                    current_entity = task.get('entity')
                    if current_entity:
                        if current_entity.get('name') == batch_name:
                            entity = current_entity
                            break
                if entity:
                    self.update_loader_list(entity)
                add_menu_list = self.prefs.get('additional menu ' + batch_name)

        else:
            self.prefs['additional menu ' + batch_name] = []

            entity = {}
            for task in tasks:
                current_entity = task.get('entity')
                if current_entity:
                    if current_entity.get('name') == batch_name:
                        entity = current_entity
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
        add_menu_list = self.prefs.get('additional menu ' + batch_name)
        for item in add_menu_list:
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
            if self.prefs['show_all']:
                menu_item['name'] = ' '*4 + 'No tasks found'
            else:
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

        entity['code'] = entity.get('name', 'no_name')
        entity_type = entity.get('type')
        entity_id = entity.get('id')
        if entity_id not in self.prefs.keys():
            self.prefs[entity_id] = {}
            self.prefs[entity_id]['show_all'] = True
        prefs = self.prefs.get(entity_id)

        tasks = []
        cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)
        
        if not isinstance(cached_tasks, list):

            # try to unregister cache and register again

            self.unregister_query()
            self.register_query()

            cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

            if not isinstance(cached_tasks, list):

                # give up

                return {}


        for cached_task in cached_tasks:
            if not cached_task.get('entity'):
                continue
            if cached_task.get('entity').get('id') != entity_id:
                continue
            tasks.append(cached_task)
        

        versions = []
        cached_versions = self.connector.async_cache_get(self.current_versions_uid)

        if not isinstance(cached_versions, list):

            # try to unregister cache and register again

            self.unregister_query()
            self.register_query()

            cached_versions = self.connector.async_cache_get(self.current_versions_uid)

            if not isinstance(cached_versions, list):

                # give up

                return {}

        for cached_version in cached_versions:
            version_entity = cached_version.get('entity')
            if not version_entity:
                continue
            if entity.get('id', 0) == version_entity.get('id'):
                versions.append(cached_version)
        

        if not self.connector.sg_human_user:
            human_user = {'id': 0}
        else:
            human_user = self.connector.sg_human_user

        menu = {}
        menu['name'] = 'Publish ' + entity.get('code') + ':'
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
            if self.prefs[entity_id]['show_all']:
                menu_item['name'] = ' '*4 + 'No tasks found'
            else:
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
                version_names = []
                version_name_lenghts = set()
                for version in versions:
                    if task_id == version.get('sg_task.Task.id'):
                        version_names.append('* ' + version.get('code'))
                        version_name_lenghts.add(len('* ' + version.get('code')))
                
                version_names = sorted(version_names)
                if len(version_names) > 5:
                    version_names = version_names[:2] + version_names[-3:]
                    version_names[2] = ' '*8 + ' '*(max(list(version_name_lenghts))//2 - 4) + '. . . . .'
                for version_name in version_names:
                    menu_item = {}
                    menu_item['name'] = ' '*8 + version_name
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
        
        # Main publishing function
        
        # First,let's check if the project folder is there
        # and if not - try to create one
        # connector takes care of storage root check and selection
        # we're going to get empty path if connector was not able to resolve it

        project_path = self.connector.resolve_project_path()

        if not project_path:
        #    message = 'Publishing stopped: Unable to resolve project path.'
        #    self.mbox.setText(message)
        #    self.mbox.exec_()
            return False

        # check if the project path is there and try to create if not

        if not os.path.isdir(project_path):
            try:
                os.makedirs(project_path)
            except Exception as e:
                message = 'Publishing stopped: Unable to create project folder %s, reason: %s' % (project_path, e)
                self.mbox.setText(message)
                self.mbox.exec_()
                return False

        # get necessary fields from currently selected export preset

        export_preset_fields = self.get_export_preset_fields(self.prefs['flame_export_presets'].get('Publish'))
        if not export_preset_fields:
            return False

        # try to publish each of selected clips
        
        versions_published = set()
        versions_failed = set()
        pb_published = dict()
        pb_failed = dict()

        for clip in selection:
            pb_info, is_cancelled = self.publish_clip(clip, entity, project_path, export_preset_fields)
            if pb_info.get('status', False):
                version_name = pb_info.get('version_name')
                versions_published.add(version_name)
                data = pb_published.get(version_name, [])
                data.append(pb_info)
                pb_published[version_name] = data
            else:
                version_name = pb_info.get('version_name')
                versions_failed.add(version_name)
                data = pb_failed.get(version_name, [])
                data.append(pb_info)
                pb_failed[version_name] = data
            if is_cancelled:
                break

        # update async cache

        self.rescan()

        # report user of the status
        
        if is_cancelled and (len(versions_published) == 0):
            return False
        elif (len(versions_published) == 0) and (len(versions_failed) > 0):
            msg = 'Failed to publish into %s versions' % len(versions_failed)
        elif (len(versions_published) > 0) and (len(versions_failed) == 0):
            msg = 'Published %s version(s)' % len(versions_published)
        else:
            msg = 'Published %s version(s), %s version(s) failed' % (len(versions_published), len(versions_failed))

        mbox = QtGui.QMessageBox()
        mbox.setText('flameMenuSG: ' + msg)

        detailed_msg = ''

        if len(versions_published) > 0:
            detailed_msg += 'Published:\n'
            for version_name in sorted(pb_published.keys()):
                pb_info_list = pb_published.get(version_name)
                for pb_info in pb_info_list:
                    detailed_msg += ' '*4 + pb_info.get('version_name') + ':\n'
                    if pb_info.get('flame_render', {}).get('flame_path'):
                        path = pb_info.get('flame_render', {}).get('flame_path')
                    else:
                        path = pb_info.get('flame_render', {}).get('path_cache')
                    detailed_msg += ' '*8 + os.path.basename(path) + '\n'
                    path_cache = pb_info.get('flame_batch', {}).get('path_cache')
                    detailed_msg += ' '*8 + os.path.basename(path_cache) + '\n'
        if len(versions_failed) > 0:
            detailed_msg += 'Failed to publish: \n'
            for version_name in sorted(pb_failed.keys()):
                pb_info_list = pb_failed.get(version_name)
                for pb_info in pb_info_list:
                    detailed_msg += ' '*4 + pb_info.get('flame_clip_name') + ':\n'
        mbox.setDetailedText(detailed_msg)
        mbox.setStyleSheet('QLabel{min-width: 500px;}')
        mbox.exec_()
        
        return True

    def publish_clip(self, clip, entity, project_path, preset_fields):

        # Publishes the clip and returns published files info and status
        
        # Each flame clip publish will create primary publish, and batch file.
        # there could be potentially secondary published defined in the future.
        # the function will return the dictionary with information on that publishes
        # to be presented to user, as well as is_cancelled flag.
        # If there's an error and current publish should be stopped that gives
        # user the possibility to stop other selected clips from being published
        # returns: (dict)pb_info , (bool)is_cancelled

        # dictionary that holds information about publish
        # publish_clip will return the list of info dicts
        # along with the status. It is purely to be able
        # to inform user of the status after we processed multpile clips
        
        pb_info = {
            'flame_clip_name': clip.name.get_value(),        # name of the clip selected in flame
            'version_name': '',     # name of a version in shotgun
            'flame_render': {       # 'flame_render' related data
                'path_cache': '',
                'pb_file_name': ''
            },
            'flame_batch': {        # 'flame_batch' related data
                'path_cache': '',
                'pb_file_name': ''
            },
            'status': False         # status of the flame clip publish
        }

        # Process info we've got from entity

        self.log('Starting publish_clip for %s with entity:' % pb_info.get('flame_clip_name'))
        self.log('\n%s' % pformat(entity))

        task = entity.get('task')
        task_entity = task.get('entity')
        task_entity_type = task_entity.get('type')
        task_entity_name = task_entity.get('name')
        task_entity_id = task_entity.get('id')
        task_step = task.get('step.Step.code')
        task_step_code = task.get('step.Step.short_name')
        if not task_step_code:
            task_step_code = task_step.upper()
        sequence = task.get('entity.Shot.sg_sequence')
        if not sequence:
            sequence_name = 'NoSequence'
        else:
            sequence_name = sequence.get('name', 'NoSequence')
        sg_asset_type = task.get('entity.Asset.sg_asset_type','NoType')
        uid = self.create_uid()    
        
        # linked .batch file path resolution
        # if the clip consists of several clips with different linked batch setups
        # fall back to the current batch setup (should probably publish all of them?)

        self.log('looking for linked batch setup...')

        import ast

        linked_batch_path = None
        comments = set()
        for version in clip.versions:
            for track in version.tracks:
                for segment in track.segments:
                    comments.add(segment.comment.get_value())
        if len(comments) == 1:
            comment = comments.pop()
            start_index = comment.find("{'batch_file': ")
            end_index = comment.find("'}", start_index)
            if (start_index > 0) and (end_index > 0):
                try:
                    linked_batch_path_dict = ast.literal_eval(comment[start_index:end_index+2])
                    linked_batch_path = linked_batch_path_dict.get('batch_file')
                except:
                    pass

        self.log('linked batch setup: %s' % linked_batch_path)

        # basic name/version detection from clip name

        self.log('parsing clip name %s' % pb_info.get('flame_clip_name'))

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

        self.log('parsed clip_name: %s' % clip_name)

        if version_number == -1:
            self.log('can not parse version, looking for batch iterations')
            version_number = len(self.flame.batch.batch_iterations) + 1
            # if (version_number == 0) and (not self.prefs.get('version_zero', False)):
            #    version_number = 1
            version_padding = 3
        
        self.log('version number: %s' % version_number)
        self.log('version_zero status: %s' % self.prefs.get('version_zero', False))

        # collect known template fields

        self.log('preset fields: %s' % pformat(preset_fields))

        if preset_fields.get('type') == 'movie':
            sg_frame = ''
        else:
            sg_frame = '%' + '{:02d}'.format(preset_fields.get('framePadding')) + 'd'

        template_fields = {}
        template_fields['Shot'] = task_entity_name
        template_fields['Asset'] = task_entity_name
        template_fields['sg_asset_type'] = sg_asset_type
        template_fields['name'] = clip_name
        template_fields['Step'] = task_step
        template_fields['Step_code'] = task_step_code
        template_fields['Sequence'] = sequence_name
        template_fields['version'] = '{:03d}'.format(version_number)
        template_fields['version_four'] = '{:04d}'.format(version_number)
        template_fields['ext'] = preset_fields.get('fileExt')
        template_fields['frame'] = sg_frame

        self.log('template fields:')
        self.log('\n%s' % pformat(template_fields))

        # compose version name from template

        version_name = self.prefs.get('templates', {}).get(task_entity_type, {}).get('version_name', {}).get('value', '')

        self.log('version name template: %s' % version_name)

        version_name = version_name.format(**template_fields)
        update_version_preview = True
        update_version_thumbnail = True
        pb_info['version_name'] = version_name

        self.log('resolved version name: %s' % version_name)  
        
        # 'flame_render'
        # start with flame_render publish first.

        self.log('starting flame_render publish...') 

        pb_file_name = task_entity_name + ', ' + clip_name

        # compose export path anf path_cache filed from template fields

        export_path = self.prefs.get('templates', {}).get(task_entity_type, {}).get('flame_render', {}).get('value', '')

        self.log('flame_render export preset: %s' % export_path)

        export_path = export_path.format(**template_fields)
        path_cache = export_path.format(**template_fields)
        export_path = os.path.join(project_path, export_path)
        path_cache = os.path.join(os.path.basename(project_path), path_cache)

        if preset_fields.get('type') == 'movie':
            export_path = export_path.replace('..', '.')
            path_cache = path_cache.replace('..', '.')

        self.log('resolved export path: %s' % export_path)
        self.log('path_cache %s' % path_cache)

        # get PublishedFileType from Shotgun
        # if it is not there - create it
        flame_render_type = self.prefs.get('templates', {}).get(task_entity_type, {}).get('flame_render', {}).get('PublishedFileType', '')
        self.log('PublishedFile type: %s, querying Shotgun' % flame_render_type)
        published_file_type = self.connector.sg.find_one('PublishedFileType', filters=[["code", "is", flame_render_type]])
        self.log('PublishedFile type: found: %s' % pformat(published_file_type))        
        if not published_file_type:
            self.log('creating PublishedFile type %s' % flame_render_type)
            published_file_type = sg.create("PublishedFileType", {"code": flame_render_type})
            self.log('created: %s' % pformat(published_file_type))

        # fill the pb_info data for 'flame_render'
        pb_info['flame_render']['path_cache'] = path_cache
        pb_info['flame_render']['pb_file_name'] = pb_file_name

        # check if we're adding publishes to existing version

        if self.connector.sg.find('Version', [
            ['entity', 'is', task_entity], 
            ['code', 'is', version_name],
            ['sg_task', 'is', {'type': 'Task', 'id': task.get('id')}]
            ]):

            self.log('found existing version with the same name')

            # do not update version thumbnail and preview
            update_version_preview = False
            update_version_thumbnail = False

            # if it is a case:
            # check if we already have published file of the same sg_published_file_type
            # and with the same name and path_cache

            task_published_files = self.connector.sg.find(
                'PublishedFile',
                [['task', 'is', {'type': 'Task', 'id': task.get('id')}]],
                ['published_file_type', 
                'path_cache', 
                'name',
                'version_number']
            )

            sg_pbf_type_flag = False
            path_cache_flag = False
            name_flag = False
            version_number_flag = False

            for task_published_file in task_published_files:
                if task_published_file.get('published_file_type', {}).get('id') == published_file_type.get('id'):
                    sg_pbf_type_flag = True
                if task_published_file.get('name') == pb_file_name:
                    name_flag = True
                if task_published_file.get('version_number') == version_number:
                    version_number_flag = True
                if task_published_file.get('path_cache') == path_cache:
                    path_cache_flag = True

            if sg_pbf_type_flag and path_cache_flag and name_flag and version_number:

                # we don't need to move down to .batch file publishing.
                
                # inform user that published file already exists:
                mbox = QtGui.QMessageBox()
                mbox.setText('Publish for flame clip %s already exists in shotgun version %s' % (pb_info.get('flame_clip_name', ''), pb_info.get('version_name', '')))
                detailed_msg = ''
                detailed_msg += 'Path: ' + os.path.join(project_path, pb_info.get('flame_render', {}).get('path_cache', ''))
                mbox.setDetailedText(detailed_msg)
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()

                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)

        # Export using main preset

        self.log('starting export form flame')

        preset_path = preset_fields.get('path')

        self.log('export preset: %s' % preset_path)

        exporter = self.flame.PyExporter()
        exporter.foreground = True
        export_clip_name, ext = os.path.splitext(os.path.basename(export_path))
        export_clip_name = export_clip_name.replace(sg_frame, '')
        if export_clip_name.endswith('.'):
            export_clip_name = export_clip_name[:-1]
        original_clip_name = clip.name.get_value()
        clip.name.set_value(export_clip_name)
        export_dir = os.path.dirname(export_path)

        if not os.path.isdir(export_dir):
            self.log('creating folders: %s' % export_dir)
            try:
                os.makedirs(export_dir)
            except:
                clip.name.set_value(original_clip_name)

                mbox = QtGui.QMessageBox()
                mbox.setText('Error publishing flame clip %s:\nunable to create destination folder.' % pb_info.get('flame_clip_name', ''))
                mbox.setDetailedText('Path: ' + export_dir)
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()
                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)

        self.log('exporting clip %s' % clip.name.get_value())
        self.log('with preset: %s' % preset_path)
        self.log('into folder: %s' % export_dir)

        try:
            exporter.export(clip, preset_path, export_dir)
            clip.name.set_value(original_clip_name)
        except:
            clip.name.set_value(original_clip_name)
            return (pb_info, True)

        # Export preview to temp folder


        # preset_dir = self.flame.PyExporter.get_presets_dir(
        #   self.flame.PyExporter.PresetVisibility.Shotgun,
        #   self.flame.PyExporter.PresetType.Movie
        # )
        # preset_path = os.path.join(preset_dir, 'Generate Preview.xml')
        preset_path = os.path.join(self.framework.prefs_folder, 'GeneratePreview.xml')
        clip.name.set_value(version_name + '_preview_' + uid)
        export_dir = '/var/tmp'
        preview_path = os.path.join(export_dir, version_name + '_preview_' + uid + '.mov')

        self.log('exporting preview %s' % clip.name.get_value())
        self.log('with preset: %s' % preset_path)
        self.log('into folder: %s' % export_dir)

        try:
            exporter.export(clip, preset_path, export_dir)
        except:
            pass

        # Set clip in and out marks and export thumbnail to temp folder

        # preset_dir = self.flame.PyExporter.get_presets_dir(
        #    self.flame.PyExporter.PresetVisibility.Shotgun,
        #    self.flame.PyExporter.PresetType.Image_Sequence
        # )
        # preset_path = os.path.join(preset_dir, 'Generate Thumbnail.xml')
        preset_path = os.path.join(self.framework.prefs_folder, 'GenerateThumbnail.xml')
        clip.name.set_value(version_name + '_thumbnail_' + uid)
        export_dir = '/var/tmp'
        thumbnail_path = os.path.join(export_dir, version_name + '_thumbnail_' + uid + '.jpg')
        clip_in_mark = clip.in_mark.get_value()
        clip_out_mark = clip.out_mark.get_value()
        clip.in_mark = self.prefs.get('poster_frame', 1)
        clip.out_mark = self.prefs.get('poster_frame', 1) + 1
        exporter.export_between_marks = True

        self.log('exporting thumbnail %s' % clip.name.get_value())
        self.log('with preset: %s' % preset_path)
        self.log('into folder: %s' % export_dir)
        self.log('poster frame: %s' % self.prefs.get('poster_frame', 1))

        try:
            exporter.export(clip, preset_path, export_dir)
        except:
            pass
        
        clip.in_mark.set_value(clip_in_mark)
        clip.out_mark.set_value(clip_out_mark)
        clip.name.set_value(original_clip_name)

        # Create version in Shotgun

        self.log('creating version in shotgun')

        version_data = dict(
            project = {'type': 'Project', 'id': self.connector.sg_linked_project_id},
            code = version_name,
            #description=item.description,
            entity = task_entity,
            sg_task = {'type': 'Task', 'id': task.get('id')},
            #sg_path_to_frames=path
        )
        version = {}
        try:
            version = self.connector.sg.create('Version', version_data)
            self.log('created Version: \n%s' % pformat(version))
        except Exception as e:
            mbox = QtGui.QMessageBox()
            mbox.setText('Error creating published file in Shotgun')
            mbox.setDetailedText(pformat(e))
            mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
            btn_Continue.setText('Continue')
            mbox.exec_()
            if mbox.clickedButton() == btn_Continue:
                return (pb_info, False)
            else:
                return (pb_info, True)        

        if os.path.isfile(thumbnail_path) and update_version_thumbnail:
            self.log('uploading thumbnail %s' % thumbnail_path)
            try:
                self.connector.sg.upload_thumbnail('Version', version.get('id'), thumbnail_path)
            except Exception as e:
                mbox = QtGui.QMessageBox()
                mbox.setText('Error uploading version thumbnail to Shotgun')
                mbox.setDetailedText(pformat(e))
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()
                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)

        if os.path.isfile(preview_path) and update_version_preview:
            self.log('uploading preview %s' % preview_path)
            try:
                self.connector.sg.upload('Version', version.get('id'), preview_path, 'sg_uploaded_movie')
            except Exception as e:
                mbox = QtGui.QMessageBox()
                mbox.setText('Error uploading version preview to Shotgun')
                mbox.setDetailedText(pformat(e))
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()
                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)


        # Create 'flame_render' PublishedFile

        self.log('creating flame_render published file in shotgun')

        published_file_data = dict(
            project = {'type': 'Project', 'id': self.connector.sg_linked_project_id},
            version_number = version_number,
            task = {'type': 'Task', 'id': task.get('id')},
            version = version,
            entity = task_entity,
            published_file_type = published_file_type,
            path = {'relative_path': path_cache, 'local_storage': self.connector.sg_storage_root},
            path_cache = path_cache,
            code = os.path.basename(path_cache),
            name = pb_file_name
        )
        try:
            published_file = self.connector.sg.create('PublishedFile', published_file_data)
        except Exception as e:
            mbox = QtGui.QMessageBox()
            mbox.setText('Error creating published file in Shotgun')
            mbox.setDetailedText(pformat(e))
            mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
            btn_Continue.setText('Continue')
            mbox.exec_()
            if mbox.clickedButton() == btn_Continue:
                return (pb_info, False)
            else:
                return (pb_info, True)


        self.log('created PublishedFile:\n%s' % pformat(published_file))
        self.log('uploading thumbnail %s' % thumbnail_path)
        try:
            self.connector.sg.upload_thumbnail('PublishedFile', published_file.get('id'), thumbnail_path)
        except Exception as e:
            mbox = QtGui.QMessageBox()
            mbox.setText('Error uploading thumbnail to Shotgun')
            mbox.setDetailedText(pformat(e))
            mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
            btn_Continue.setText('Continue')
            mbox.exec_()
            if mbox.clickedButton() == btn_Continue:
                return (pb_info, False)
            else:
                return (pb_info, True)        

        pb_info['status'] = True

        # check what we've actually exported and get start and end frames from there
        # this won't work for movie, so check the preset first
        # this should be moved in a separate function later

        self.log('getting start and end frames from exported clip')
        
        flame_path = ''
        flame_render_path_cache = pb_info.get('flame_render', {}).get('path_cache', '')
        flame_render_export_dir = os.path.join(os.path.dirname(project_path), os.path.dirname(flame_render_path_cache))

        if preset_fields.get('type', 'image') == 'image':
            import fnmatch

            try:
                file_names = [f for f in os.listdir(flame_render_export_dir) if os.path.isfile(os.path.join(flame_render_export_dir, f))]
            except:
                file_names = []
                                    
            frame_pattern = re.compile(r"^(.+?)([0-9#]+|[%]0\dd)$")
            root, ext = os.path.splitext(os.path.basename(flame_render_path_cache))
            match = re.search(frame_pattern, root)
            if match:
                pattern = os.path.join("%s%s" % (re.sub(match.group(2), "*", root), ext))
                files = list()
                for file_name in file_names:
                    if fnmatch.fnmatch(file_name, pattern):
                        files.append(os.path.join(export_dir, file_name))
                
                if files:
                    file_roots = [os.path.splitext(f)[0] for f in files]
                    frame_padding = len(re.search(frame_pattern, file_roots[0]).group(2))
                    offset = len(match.group(1))
                    frames = list()
                    for f in file_roots:
                        try:
                            frame = int(os.path.basename(f)[offset:offset+frame_padding])
                        except:
                            continue
                        frames.append(frame)

                    if frames:
                        min_frame = min(frames)
                        self.log('start frame: %s' % min_frame)
                        max_frame = max(frames)
                        self.log('end_frame %s' % min_frame)
                        format_str = "[%%0%sd-%%0%sd]" % (frame_padding, frame_padding)
                        frame_spec = format_str % (min_frame, max_frame)
                        flame_file_name = "%s%s%s" % (match.group(1), frame_spec, ext)
                        flame_path = os.path.join(export_dir, flame_file_name)

                        self.connector.sg.update('Version', version.get('id'), {'sg_first_frame': min_frame, 'sg_last_frame': max_frame})

            pb_info['flame_render']['flame_path'] = flame_path
        
        elif preset_fields.get('type', 'image') == 'movie':
            pass
            # placeholder for movie export

        # publish .batch file
        # compose batch export path and path_cache filed from template fields

        self.log('starting .batch file publish')

        export_path = self.prefs.get('templates', {}).get(task_entity_type, {}).get('flame_batch', {}).get('value', '')
        export_path = export_path.format(**template_fields)
        path_cache = export_path.format(**template_fields)
        export_path = os.path.join(project_path, export_path)
        path_cache = os.path.join(os.path.basename(project_path), path_cache)

        self.log('resolved export path: %s' % export_path)
        self.log('path_cache %s' % path_cache)

        pb_info['flame_batch']['path_cache'] = path_cache
        pb_info['flame_batch']['pb_file_name'] = task_entity_name
        
        # copy flame .batch file linked to the clip or save current one if not resolved from comments

        export_dir = os.path.dirname(export_path)
        if not os.path.isdir(export_dir):
            self.log('creating folders: %s' % export_dir)
            try:
                os.makedirs(export_dir)
            except:
                clip.name.set_value(original_clip_name)

                mbox = QtGui.QMessageBox()
                mbox.setText('Error publishing flame clip %s:\nunable to create destination .batch folder.' % pb_info.get('flame_clip_name', ''))
                mbox.setDetailedText('Path: ' + export_dir)
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()
                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)

        if linked_batch_path:

            self.log('copying linked .batch file')
            self.log('from %s' % linked_batch_path)
            slef.log('to %s' % export_path)

            src, ext = os.path.splitext(linked_batch_path)
            dest, ext = os.path.splitext(export_path)
            if os.path.isfile(linked_batch_path) and  os.path.isdir(src):
                try:
                    from subprocess import call
                    call(['cp', '-a', src, dest])
                    call(['cp', '-a', linked_batch_path, export_path])
                except:
                    mbox = QtGui.QMessageBox()
                    mbox.setText('Error publishing flame clip %s:\nunable to copy flame batch.' % pb_info.get('flame_clip_name', ''))
                    mbox.setDetailedText('Path: ' + export_path)
                    mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                    mbox.setStyleSheet('QLabel{min-width: 400px;}')
                    btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                    btn_Continue.setText('Continue')
                    mbox.exec_()
                    if mbox.clickedButton() == btn_Continue:
                        return (pb_info, False)
                    else:
                        return (pb_info, True)
            else:
                self.log('no linked .batch file found on filesystem')
                self.log('saving current batch to: %s' % export_path)
                self.flame.batch.save_setup(export_path)
        else:
            self.log('no linked .batch file')
            self.log('saving current batch to: %s' % export_path)
            self.flame.batch.save_setup(export_path)

        # get published file type for Flame Batch or create a published file type on the fly

        flame_batch_type = self.prefs.get('templates', {}).get(task_entity_type, {}).get('flame_batch', {}).get('PublishedFileType', '')
        self.log('PublishedFile type: %s, querying Shotgun' % flame_batch_type)
        published_file_type = self.connector.sg.find_one('PublishedFileType', filters=[["code", "is", flame_batch_type]])
        self.log('PublishedFile type: found: %s' % pformat(published_file_type))
        if not published_file_type:
            self.log('creating PublishedFile type %s' % flame_render_type)
            try:
                published_file_type = self.connector.sg.create("PublishedFileType", {"code": flame_batch_type})
            except Exception as e:
                mbox = QtGui.QMessageBox()
                mbox.setText('Error creating published file type in Shotgun')
                mbox.setDetailedText(pformat(e))
                mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
                btn_Continue.setText('Continue')
                mbox.exec_()
                if mbox.clickedButton() == btn_Continue:
                    return (pb_info, False)
                else:
                    return (pb_info, True)

            self.log('created: %s' % pformat(published_file_type))

        # update published file data and create PublishedFile for flame batch

        self.log('creating flame_batch published file in shotgun')

        published_file_data['published_file_type'] = published_file_type
        published_file_data['path'] =  {'relative_path': path_cache, 'local_storage': self.connector.sg_storage_root}
        published_file_data['path_cache'] = path_cache
        published_file_data['code'] = os.path.basename(path_cache)
        published_file_data['name'] = task_entity_name
        try:
            published_file = self.connector.sg.create('PublishedFile', published_file_data)
        except Exception as e:
            mbox = QtGui.QMessageBox()
            mbox.setText('Error creating published file in Shotgun')
            mbox.setDetailedText(pformat(e))
            mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
            btn_Continue.setText('Continue')
            mbox.exec_()
            if mbox.clickedButton() == btn_Continue:
                return (pb_info, False)
            else:
                return (pb_info, True)
        
        self.log('created PublishedFile:\n%s' % pformat(published_file))
        self.log('uploading thumbnail %s' % thumbnail_path)
        
        try:
            self.connector.sg.upload_thumbnail('PublishedFile', published_file.get('id'), thumbnail_path)
        except Exception as e:
            mbox = QtGui.QMessageBox()
            mbox.setText('Error uploading thumbnail to Shotgun')
            mbox.setDetailedText(pformat(e))
            mbox.setStandardButtons(QtGui.QMessageBox.Ok|QtGui.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtGui.QMessageBox.Ok)
            btn_Continue.setText('Continue')
            mbox.exec_()
            if mbox.clickedButton() == btn_Continue:
                return (pb_info, False)
            else:
                return (pb_info, True)

        # clean-up preview and thumbnail files

        self.log('cleaning up preview and thumbnail files')

        try:
            os.remove(thumbnail_path)
            os.remove(preview_path)
        except:
            self.log('cleaning up failed')
        
        self.log('returning info:\n%s' % pformat(pb_info))

        return (pb_info, False)

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
        
        # get current tasks form async cache

        cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

        if not isinstance(cached_tasks, list):

            # try to unregister cache and register again

            self.unregister_query()
            self.register_query()

            cached_tasks = self.connector.async_cache_get(self.current_tasks_uid)

            if not isinstance(cached_tasks, list):

                # give up

                return {}


        # remove tasks without entities and filter if user_only
        
        user_id = 0
        if self.connector.sg_human_user:
            user_id = self.connector.sg_human_user.get('id', 0)
        tasks = []
        for cached_task in cached_tasks:
            if not cached_task.get('entity'):
                continue
            if user_only:
                if not cached_task.get('task_assignees'):
                    continue
                else:
                    task_assignees_ids = [assignee.get('id') for assignee in cached_task.get('task_assignees', [])]
                    if user_id not in task_assignees_ids:
                        continue

            tasks.append(cached_task)            

        # group entities by id

        entities_by_id = {task.get('entity').get('id'):task.get('entity') for task in tasks}
        
        shots = []
        assets = []
        for entity_id in sorted(entities_by_id.keys()):
            entity = entities_by_id.get(entity_id)
            if entity.get('type') == 'Shot':
                shots.append({'code': entity.get('name'), 'id': entity_id, 'type': 'Shot'})
            elif entity.get('type') == 'Asset':
                assets.append({'code': entity.get('name'), 'id': entity_id, 'type': 'Asset'})
        
        return {'Asset': assets, 'Shot': shots}
        
        '''
        sg = self.connector.sg

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
        '''

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

    def create_export_presets(self):

        preview_preset = '''<?xml version="1.0"?>
        <preset version="9">
        <type>movie</type>
        <comment>Shotgun movie preview</comment>
        <movie>
            <fileType>QuickTime</fileType>
            <namePattern>&lt;name&gt;</namePattern>
            <yuvHeadroom>False</yuvHeadroom>
            <yuvColourSpace>PCS_UNKNOWN</yuvColourSpace>
        </movie>
        <video>
            <fileType>QuickTime</fileType>
            <codec>33622016</codec>
            <codecProfile>
                <rootPath>/opt/Autodesk/mediaconverter/</rootPath>
                <targetVersion>2020.2</targetVersion>
                <pathSuffix>/profiles/.33622016/HDTV_720p_8Mbits.cdxprof</pathSuffix>
            </codecProfile>
            <namePattern>&lt;name&gt;</namePattern>
            <overwriteWithVersions>False</overwriteWithVersions>
            <lutState>
                <Setup>
                    <Base>
                        <Version>18</Version>
                        <Note></Note>
                        <Expanded>False</Expanded>
                        <ScrollBar>0</ScrollBar>
                        <Frames>79</Frames>
                        <Current_Time>1</Current_Time>
                        <Input_DataType>4</Input_DataType>
                        <ClampMode>0</ClampMode>
                        <AdapDegrad>False</AdapDegrad>
                        <ReadOnly>False</ReadOnly>
                        <NoMediaHandling>1</NoMediaHandling>
                        <UsedAsTransition>False</UsedAsTransition>
                        <FrameBounds W="3200" H="1800" X="0" Y="0" SX="26.666666666666664" SY="15"/>
                    </Base>
                    <State>
                        <LogLinTargetPixelFormat>143</LogLinTargetPixelFormat>
                        <LogLinPropRefWhite>True</LogLinPropRefWhite>
                        <LogLinPropRefBlack>True</LogLinPropRefBlack>
                        <LogLinPropHighlight>True</LogLinPropHighlight>
                        <LogLinPropShadow>True</LogLinPropShadow>
                        <LogLinPropSoftclip>True</LogLinPropSoftclip>
                        <LogLinPropDispGamma>True</LogLinPropDispGamma>
                        <LogLinPropFilmGamma>True</LogLinPropFilmGamma>
                        <LogLinPropExposure>True</LogLinPropExposure>
                        <LogLinPropDefog>True</LogLinPropDefog>
                        <LogLinPropKneeLow>True</LogLinPropKneeLow>
                        <LogLinPropKneeHigh>True</LogLinPropKneeHigh>
                        <LogLinAdjustPropLuts>True</LogLinAdjustPropLuts>
                        <LogLinPropLowRoll>True</LogLinPropLowRoll>
                        <LogLinPropLowCon>True</LogLinPropLowCon>
                        <LogLinPropContrast>True</LogLinPropContrast>
                        <LogLinPropHighCon>True</LogLinPropHighCon>
                        <LogLinPropHighRoll>True</LogLinPropHighRoll>
                        <LogLinHasBeenActivated>True</LogLinHasBeenActivated>
                        <LutsBuilder>
                            <LutsBuilder LutFileVersion="3">
                                <ConversionType>0</ConversionType>
                                <GammaType>1</GammaType>
                                <BasicMode>6</BasicMode>
                                <AdjustMode>False</AdjustMode>
                                <RedLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </RedLut>
                                <GreenLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </GreenLut>
                                <BlueLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </BlueLut>
                                <ColorTransformBuilder>
                                    <ColorTransformBuilder CTBVersion="1.400000">
                                        <CTBCustom>False</CTBCustom>
                                        <CTBInvert>False</CTBInvert>
                                        <CTBSolo>False</CTBSolo>
                                        <CTBSelected>-1</CTBSelected>
                                        <CTBIsColourSpaceConversion>False</CTBIsColourSpaceConversion>
                                        <CTBSrcColourSpace></CTBSrcColourSpace>
                                        <CTBDstColourSpace>Unknown</CTBDstColourSpace>
                                        <CTBTaggedColourSpace>From Source</CTBTaggedColourSpace>
                                        <CTBViewTransformEnabled>True</CTBViewTransformEnabled>
                                        <CTBVTSrcCS>From Source</CTBVTSrcCS>
                                        <CTBVTViewCS>From Rules</CTBVTViewCS>
                                        <CTBVTDispCS>sRGB display</CTBVTDispCS>
                                        <CTBItems/>
                                    </ColorTransformBuilder>
                                </ColorTransformBuilder>
                            </LutsBuilder>
                        </LutsBuilder>
                    </State>
                </Setup>
            </lutState>
            <resize>
                <resizeType>fit</resizeType>
                <resizeFilter>lanczos</resizeFilter>
                <width>720</width>
                <height>400</height>
                <bitsPerChannel>8</bitsPerChannel>
                <numChannels>3</numChannels>
                <floatingPoint>False</floatingPoint>
                <bigEndian>False</bigEndian>
                <pixelRatio>1</pixelRatio>
                <scanFormat>P</scanFormat>
            </resize>
        </video>
        <audio>
            <fileType>QuickTime</fileType>
            <codec>4027060226</codec>
            <codecProfile>
                <rootPath>/opt/Autodesk/mediaconverter/</rootPath>
                <targetVersion>2020.2</targetVersion>
                <pathSuffix>/profiles/.4027060226/160 kbps.cdxprof</pathSuffix>
            </codecProfile>
            <namePattern>&lt;name&gt;</namePattern>
            <mixdown>To2</mixdown>
            <sampleRate>-1</sampleRate>
            <bitDepth>-1</bitDepth>
        </audio>
        </preset>'''

        thumbnail_preset = '''<?xml version="1.0" encoding="UTF-8"?>
        <preset version="9">
        <type>image</type>
        <comment>Shotgun thumbnail</comment>
        <video>
            <fileType>Jpeg</fileType>
            <codec>923688</codec>
            <codecProfile></codecProfile>
            <namePattern>&lt;name&gt;.</namePattern>
            <compressionQuality>100</compressionQuality>
            <transferCharacteristic>2</transferCharacteristic>
            <publishLinked>0</publishLinked>
            <lutState>
                <Setup>
                    <Base>
                        <Version>18</Version>
                        <Note></Note>
                        <Expanded>False</Expanded>
                        <ScrollBar>0</ScrollBar>
                        <Frames>79</Frames>
                        <Current_Time>1</Current_Time>
                        <Input_DataType>4</Input_DataType>
                        <ClampMode>0</ClampMode>
                        <AdapDegrad>False</AdapDegrad>
                        <ReadOnly>False</ReadOnly>
                        <NoMediaHandling>1</NoMediaHandling>
                        <UsedAsTransition>False</UsedAsTransition>
                        <FrameBounds W="3200" H="1800" X="0" Y="0" SX="26.666666666666664" SY="15"/>
                    </Base>
                    <State>
                        <LogLinTargetPixelFormat>143</LogLinTargetPixelFormat>
                        <LogLinPropRefWhite>True</LogLinPropRefWhite>
                        <LogLinPropRefBlack>True</LogLinPropRefBlack>
                        <LogLinPropHighlight>True</LogLinPropHighlight>
                        <LogLinPropShadow>True</LogLinPropShadow>
                        <LogLinPropSoftclip>True</LogLinPropSoftclip>
                        <LogLinPropDispGamma>True</LogLinPropDispGamma>
                        <LogLinPropFilmGamma>True</LogLinPropFilmGamma>
                        <LogLinPropExposure>True</LogLinPropExposure>
                        <LogLinPropDefog>True</LogLinPropDefog>
                        <LogLinPropKneeLow>True</LogLinPropKneeLow>
                        <LogLinPropKneeHigh>True</LogLinPropKneeHigh>
                        <LogLinAdjustPropLuts>True</LogLinAdjustPropLuts>
                        <LogLinPropLowRoll>True</LogLinPropLowRoll>
                        <LogLinPropLowCon>True</LogLinPropLowCon>
                        <LogLinPropContrast>True</LogLinPropContrast>
                        <LogLinPropHighCon>True</LogLinPropHighCon>
                        <LogLinPropHighRoll>True</LogLinPropHighRoll>
                        <LogLinHasBeenActivated>True</LogLinHasBeenActivated>
                        <LutsBuilder>
                            <LutsBuilder LutFileVersion="3">
                                <ConversionType>0</ConversionType>
                                <GammaType>1</GammaType>
                                <BasicMode>6</BasicMode>
                                <AdjustMode>False</AdjustMode>
                                <RedLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </RedLut>
                                <GreenLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </GreenLut>
                                <BlueLut>
                                    <Cineon Version="1">
                                        <ConversionType>0</ConversionType>
                                        <ReferenceWhite>0.669599</ReferenceWhite>
                                        <ReferenceBlack>0.092864</ReferenceBlack>
                                        <Highlight>1</Highlight>
                                        <Shadow>0</Shadow>
                                        <Softclip>0</Softclip>
                                        <FilmGamma>0.600000</FilmGamma>
                                        <GammaCorrection>0.450000</GammaCorrection>
                                        <Defog>0</Defog>
                                        <KneeLow>0</KneeLow>
                                        <KneeHigh>0</KneeHigh>
                                        <Exposure>0</Exposure>
                                        <LowRoll>0</LowRoll>
                                        <LowCon>0</LowCon>
                                        <Contrast>0</Contrast>
                                        <HighCon>0</HighCon>
                                        <HighRoll>0</HighRoll>
                                        <Encoding>9</Encoding>
                                        <Invert>0</Invert>
                                    </Cineon>
                                </BlueLut>
                                <ColorTransformBuilder>
                                    <ColorTransformBuilder CTBVersion="1.400000">
                                        <CTBCustom>False</CTBCustom>
                                        <CTBInvert>False</CTBInvert>
                                        <CTBSolo>False</CTBSolo>
                                        <CTBSelected>-1</CTBSelected>
                                        <CTBIsColourSpaceConversion>False</CTBIsColourSpaceConversion>
                                        <CTBSrcColourSpace></CTBSrcColourSpace>
                                        <CTBDstColourSpace>Unknown</CTBDstColourSpace>
                                        <CTBTaggedColourSpace>From Source</CTBTaggedColourSpace>
                                        <CTBViewTransformEnabled>True</CTBViewTransformEnabled>
                                        <CTBVTSrcCS>From Source</CTBVTSrcCS>
                                        <CTBVTViewCS>From Rules</CTBVTViewCS>
                                        <CTBVTDispCS>sRGB display</CTBVTDispCS>
                                        <CTBItems/>
                                    </ColorTransformBuilder>
                                </ColorTransformBuilder>
                            </LutsBuilder>
                        </LutsBuilder>
                    </State>
                </Setup>
            </lutState>
            <resize>
            <resizeType>fit</resizeType>
            <resizeFilter>lanczos</resizeFilter>
            <width>720</width>
            <height>400</height>
            <bitsPerChannel>8</bitsPerChannel>
            <numChannels>3</numChannels>
            <floatingPoint>0</floatingPoint>
            <bigEndian>1</bigEndian>
            <pixelRatio>1.000000</pixelRatio>
            <scanFormat>P</scanFormat>
            </resize>
            </video>
        <name>
        <framePadding>0</framePadding>
        <startFrame>1</startFrame>
        <useTimecode>1</useTimecode>
        </name>
        </preset>'''

        preview_preset_file_path = os.path.join(self.framework.prefs_folder, 'GeneratePreview.xml')
        if not os.path.isfile(preview_preset_file_path):
            try:
                with open(preview_preset_file_path, 'a') as preview_preset_file:
                    preview_preset_file.write(preview_preset)
                    preview_preset_file.close()
            except:
                pass
        thumbnail_preset_file_path = os.path.join(self.framework.prefs_folder, 'GenerateThumbnail.xml')
        if not os.path.isfile(thumbnail_preset_file_path):
            try:
                with open(thumbnail_preset_file_path, 'a') as thumbnail_preset_file:
                    thumbnail_preset_file.write(thumbnail_preset)
                    thumbnail_preset_file.close()
            except:
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

    def register_query(self, *args, **kwargs):
        if self.connector.sg_linked_project_id and self.current_tasks_uid:
            # check if project id match
            try:
                filters = self.connector.async_cache.get(self.current_tasks_uid).get('query').get('filters')
                project_id = filters[0][2]
            except:
                return False

            if project_id != self.connector.sg_linked_project_id:
                
                # unregister old id and register new one
                
                self.unregister_query()

                self.current_tasks_uid = self.connector.async_cache_register({
                    'entity': 'Task',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': [
                        'content',
                        'step.Step.code',
                        'step.Step.short_name',
                        'task_assignees',
                        'project.Project.id',
                        'entity',
                        'entity.Asset.sg_asset_type',
                        'entity.Shot.sg_sequence'
                    ]
                })
                self.current_versions_uid = self.connector.async_cache_register({
                    'entity': 'Version',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': [
                        'code',
                        'sg_task.Task.id',
                        'entity'
                    ]
                })
                return True
            else:
                return False
            
        elif self.connector.sg_linked_project_id and not self.current_tasks_uid:
            # register new query from scratch
            self.current_tasks_uid = self.connector.async_cache_register({
                    'entity': 'Task',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': [
                        'content',
                        'step.Step.code',
                        'step.Step.short_name',
                        'task_assignees',
                        'project.Project.id',
                        'entity',
                        'entity.Asset.sg_asset_type',
                        'entity.Shot.sg_sequence'
                    ]
            # ['entity', 'task_assignees']
            })
            self.current_versions_uid = self.connector.async_cache_register({
                    'entity': 'Version',
                    'filters': [['project.Project.id', 'is', self.connector.sg_linked_project_id]],
                    'fields': [
                        'code',
                        'sg_task.Task.id',
                        'entity'
                    ]
            })          
            return True
        elif self.current_tasks_uid and not self.connector.sg_linked_project_id:
            # unregister current uid
            self.connector.async_cache_unregister(self.current_tasks_uid)
            return True
        else:
            return False

    def unregister_query(self, *args, **kwargs):

        # un-registers async cache requests
        
        self.connector.async_cache_unregister(self.current_tasks_uid)
        self.connector.async_cache_unregister(self.current_versions_uid)

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        self.connector.async_cache_get(self.current_tasks_uid, True)
        self.connector.async_cache.get(self.current_versions_uid, True)

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log('Rescan Python Hooks')
            if self.connector:
                self.connector.rescan_flag = False

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

# Exception handler
def exeption_handler(exctype, value, tb):
    from PySide2 import QtWidgets
    import traceback
    msg = 'flameMenuSG: Python exception %s in %s' % (value, exctype)
    mbox = QtWidgets.QMessageBox()
    mbox.setText(msg)
    mbox.setDetailedText(pformat(traceback.format_exception(exctype, value, tb)))
    mbox.setStyleSheet('QLabel{min-width: 800px;}')
    mbox.exec_()
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exeption_handler

# register clean up logic to be called at Flame exit
def cleanup(apps, app_framework, shotgunConnector):
    if apps:
        if DEBUG:
            print ('[DEBUG %s] unloading apps:\n%s' % ('flameMenuSG', pformat(apps)))
        while len(apps):
            app = apps.pop()
            if DEBUG:
                print ('[DEBUG %s] unloading: %s' % ('flameMenuSG', app.name))
            del app        
        del apps

    if shotgunConnector:
        shotgunConnector.terminate_loops()
        del shotgunConnector

    if app_framework:
        print ('PYTHON\t: %s cleaning up' % app_framework.bundle_name)
        app_framework.save_prefs()
        del app_framework

atexit.register(cleanup, apps, app_framework, shotgunConnector)

def load_apps(apps, app_framework, shotgunConnector):
    apps.append(flameMenuProjectconnect(app_framework, shotgunConnector))
    apps.append(flameBatchBlessing(app_framework))
    apps.append(flameMenuNewBatch(app_framework, shotgunConnector))
    apps.append(flameMenuBatchLoader(app_framework, shotgunConnector))
    apps.append(flameMenuPublisher(app_framework, shotgunConnector))
    app_framework.apps = apps
    if DEBUG:
        print ('[DEBUG %s] loaded:\n%s' % (app_framework.bundle_name, pformat(apps)))

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
    start = time.time()
    menu = []
    flameMenuProjectconnectApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuProjectconnect':
            flameMenuProjectconnectApp = app
    if flameMenuProjectconnectApp:
        menu.append(flameMenuProjectconnectApp.build_menu())
    if menu:
        menu[0]['actions'].append({'name': __version__, 'isEnabled': False})

    if DEBUG:
        print('main menu update took %s' % (time.time() - start))

    if app_framework:
        menu_auto_refresh = app_framework.prefs_global.get('menu_auto_refresh', {})
        if menu_auto_refresh.get('main_menu', False):
            try:
                import flame
                flame.execute_shortcut('Rescan Python Hooks')
            except:
                pass
    return menu

def get_media_panel_custom_ui_actions():
    start = time.time()
    menu = []
    for app in apps:
        if app.__class__.__name__ == 'flameMenuNewBatch':
            app_menu = app.build_menu()
            if app_menu:
                menu.append(app_menu)
        if app.__class__.__name__ == 'flameMenuPublisher':
            app_menu = app.build_menu()
            if app_menu:
                menu.extend(app_menu)
    if DEBUG:
        print('media panel menu update took %s' % (time.time() - start))

    if app_framework:
        menu_auto_refresh = app_framework.prefs_global.get('menu_auto_refresh', {})
        if menu_auto_refresh.get('media_panel', False):
            try:
                import flame
                flame.execute_shortcut('Rescan Python Hooks')
            except:
                pass
    return menu

def get_batch_custom_ui_actions():
    start = time.time()
    menu = []
    flameMenuBatchLoaderApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuBatchLoader':
            flameMenuBatchLoaderApp = app
    if flameMenuBatchLoaderApp:
        app_menu = flameMenuBatchLoaderApp.build_menu()
        if app_menu:
            for menuitem in app_menu:
                menu.append(menuitem)

    if DEBUG:
        print('batch menu update took %s' % (time.time() - start))

    if app_framework:
        menu_auto_refresh = app_framework.prefs_global.get('menu_auto_refresh', {})
        if menu_auto_refresh.get('batch', False):
            try:
                import flame
                flame.execute_shortcut('Rescan Python Hooks')
            except:
                pass
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
    batch_file_name = flame.batch.name.get_value() + '_' + current_batch_uid + '.batch'
    while os.path.isfile(batch_file_name):
        current_batch_uid = flameBatchBlessingApp.create_batch_uid()
        batch_file_name = flame.batch.name.get_value() + '_' + current_batch_uid + '.batch'

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
    batch_setup_name = flame.batch.name.get_value() + '_' + current_batch_uid
    path = os.path.join(flame_batch_path, batch_setup_name)
    if not info.get('aborted'):
        print ('saving batch %s.batch' % path)
        flame.batch.save_setup(path)
        userData['batch_setup_name'] = batch_setup_name
        userData['batch_setup_file'] = path + '.batch'
    else:
        userData['batch_setup_name'] = 'Render aborted by user'

    flameBatchBlessingApp.bless_batch_renders(userData)
