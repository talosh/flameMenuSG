import os
import sys
import sgtk
import time
import multiprocessing
import signal
import atexit
import base64
import uuid
from datetime import datetime
from pprint import pprint

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
        self.prefs = {}
        self.name = self.__class__.__name__
        self._framework.prefs[self.name] = self.prefs
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('calling %s' % name)
        return method

    def log(self, message):
        if self.debug:
            print ('[DEBUG %s] %s' % (self._framework.bundle_name, message))

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
        user = self.get_user()
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
    
    def build_menu(self):
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

class flameBatchBlessing(flameApp):
    def __init__(self, framework):
        flameApp.__init__(self, framework)
        self.root_folder = self.batch_setup_root_folder()

    def batch_setup_root_folder(self):
        import flame
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
                print ('PYTHON\t: %s can not create %s' % (bundle_name, flame_batch_path))
                return False
        
        return flame_batch_path

    def collect_clip_uids(self, render_dest):
        import flame
        '''
        collects clip uids from locations specified in render_dest dictionary
        returns:    dictionary of lists of clip uid's at the locations specified
                    in render_dest dictionary.
                    clip_uids = {
                                'Batch Reels': {
                                    'BatchReel Name': [uid1, uid2]
                                    }
                                'Batch Shelf Reels': {
                                    'Shelf Reel Name 1': [uid3, uid4]
                                    'Shelf Reel Name 2': [uid5, uid6, uid7]
                                    }
                                'Libraries': {
                                    'Library Name 3': [uid8, uid9]
                                }
                                'Reel Groups': {
                                    'Reel Group Name 1': {
                                        'Reel 1': []
                                        'Reel 2: []
                                    }
                                    'Reel Group Name 2': {
                                        'Reel 1': []
                                        'Reel 2: []
                                    } 
    
                                }
                    }
        '''

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
        '''
        finds clips that was not in the render destionations before
        abd blesses them by adding batch_setup_name to the comments
        '''

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
                                        print ('PYTHON\t: %s unable to bless %s' % (bundle_name, clip.name))
                                        print ('PYTHON\t: %s libraries are protected from editing' % bundle_name)
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
        '''
        generates UUID for the batch setup
        '''
        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
        timestamp = (datetime.now()).strftime('%y%m%d%H%M')
        return timestamp + uid[:1]

class flameMenuNewBatch(flameShotgunApp):
    def __init__(self, framework):
        flameShotgunApp.__init__(self, framework)
        self.prefs['show_all'] = False
        self.prefs['current_page'] = 0
        self.prefs['menu_max_items_per_page'] = 128

    def __getattr__(self, name):
        def method(*args, **kwargs):
            entity = self.dynamic_menu_data.get(name)
            if entity:
                self.create_new_batch(entity)
                self.rescan()
        return method

    def build_menu(self):
        if not self.sg_user:
            return None
        if not self.sg_linked_project:
            return None

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
                entities_by_name[entity.get('code')] = entity
            for entity_name in sorted(entities_by_name.keys()):
                entity = entities_by_name.get(entity_name)
                menu_item = {}
                if entity.get('code') in batch_groups:
                    menu_item['name'] = '  * ' + entity.get('code')
                else:
                    menu_item['name'] = '     ' + entity.get('code')

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
        sg = self.sg_user.create_sg_connection()
        project_id = self.get_shotgun_project_id(self.sg_linked_project)
        task_filters = [['project.Project.id', 'is', project_id]]

        if user_only:
            human_user = sg.find_one('HumanUser', 
                [['login', 'is', self.sg_user.login]],
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

    def create_new_batch(self, entity):        
        sg = self.sg_user.create_sg_connection()
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
            if step_short_name in steps_to_ignore:
                continue
            if step_short_name not in publishes_by_step.keys():
                publishes_by_step[step_short_name] = []
            published_file_type = publish.get('published_file_type')
            if published_file_type:
                published_file_type_name = published_file_type.get('name')
            if published_file_type_name in types_to_include:
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
            storage_root = self.get_storage_root(publish.get('path_cache_storage'))
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
        self.rescan()

    def page_fwd(self, *args, **kwargs):
        self.prefs['current_page'] += 1

    def page_bkw(self, *args, **kwargs):
        self.prefs['current_page'] = max(self.prefs['current_page'] - 1, 0)

    def refresh(self, *args, **kwargs):
        # self._sg_signout_marker = os.path.join(self.framework.bundle_location, self.framework.name + '.signout')
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

    def rescan(self, *args, **kwargs):
        self.refresh()
        self._framework.rescan()




print ('PYTHON\t: %s initializing' % bundle_name)
app_framework = flameAppFramework()
apps = []

# --- FLAME HOOKS ---

def app_initialized(project_name):
    print ('===== app_initialized hook')
    print ('apps lenghth = %s' % len(apps))
    for n in range (0, len(apps)):
        print ('n = %s' % n)
        app = apps.pop(n)
        print (type(app))
        del app
    
    apps.append(flameMenuProjectconnect(app_framework))
    apps.append(flameBatchBlessing(app_framework))
    apps.append(flameMenuNewBatch(app_framework))
    print (apps)

def get_main_menu_custom_ui_actions():
    menu = []
    flameMenuProjectconnectApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuProjectconnect':
            flameMenuProjectconnectApp = app
    if flameMenuProjectconnectApp:
        menu.append(flameMenuProjectconnectApp.build_menu())
        flameMenuProjectconnectApp.refresh()
    return menu
            
def get_media_panel_custom_ui_actions():
    menu = []
    flameMenuNewBatchApp = None
    for app in apps:
        if app.__class__.__name__ == 'flameMenuNewBatch':
            flameMenuNewBatchApp = app
    if flameMenuNewBatchApp:
        flameMenuNewBatchApp.refresh()
        menu.append(flameMenuNewBatchApp.build_menu())
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