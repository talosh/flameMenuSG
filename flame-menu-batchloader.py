import os
import sys
import inspect

import sgtk

from pprint import pprint

menu_group_name = 'Menu(SG)'
bunlde_location = '/var/tmp'
storage_root = '/Volumes/projects'
types_to_include = [
            'Image Sequence',
            'Flame Render'
        ]


class flameAppFramework(object):
    def __init__(self):
        self._name = 'flameMenuSG'
        self._prefs = {}
        self._bundle_location = bunlde_location
        try:
            import flame
            self._flame = flame
        except:
            self._flame = None
    
    def rescan(self):
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
        self.name = os.path.splitext(os.path.basename(__file__))[0]
        self._framework = framework
        self.flame = fw.flame
        self.menu_group_name = menu_group_name
        self.dynamic_menu_data = {}
        self.prefs = {}
        self._framework.prefs[self.name] = self.prefs
    
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

    def get_storage_root(self, path_cache_storage):
        # just a dummy at the moment
        # should get it from project pipeline configuration
        return storage_root    

class menuBatchLoader(flameShotgunApp):
    def __init__(self, framework):
        flameShotgunApp.__init__(self, framework)
        self.prefs['show_all'] = False
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
        if not self.sg_user:
            return None
        if not self.sg_linked_project:
            return None

        batch_name = self.flame.batch.name.get_value()
        if (batch_name + '_batch_loader_add') in self.prefs.keys():
            add_menu_list = self.prefs.get(batch_name + '_batch_loader_add')
        else:
            self.prefs[batch_name + '_batch_loader_add'] = []
            sg = self.sg_user.create_sg_connection()
            project_id = self.get_shotgun_project_id(self.sg_linked_project)
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
            add_menu_list = self.prefs.get(batch_name + '_batch_loader_add')

        menus = []
        menus.append(self.build_addremove_menu())

        for entity in add_menu_list:
            batch_loader_menu = self.build_batch_loader_menu(entity)
            if batch_loader_menu:
                menus.append(batch_loader_menu)

        return menus

    def build_addremove_menu(self):
        if not self.sg_user:
            return None
        if not self.sg_linked_project:
            return None

        flame_project_name = self.flame.project.current_project.name
        batch_name = self.flame.batch.name.get_value()
        entities_to_mark = []
        batch_loader_additional = self.prefs.get(batch_name + '_batch_loader_add')
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
        sg = self.sg_user.create_sg_connection()
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
            
            for publish in publishes:
                step = publish.get('task.Task.step.Step.code')
                if not step:
                    step = ''
                if step == step_name:
                    published_file_type = publish.get('published_file_type')
                    if published_file_type:
                        published_file_type_name = published_file_type.get('name')
                    if published_file_type_name in types_to_include:
                        name = publish.get('name')
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
        add_list = self.prefs.get(batch_name + '_batch_loader_add')
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
        self.prefs[batch_name + '_batch_loader_add'] = add_list

    def load_into_batch(self, entity):
        path_cache = entity.get('path_cache')
        if not path_cache:
            return
        
        storage_root = self.get_storage_root(entity.get('path_cache_storage'))
        path = os.path.join(storage_root, path_cache)
        flame_path = self.build_flame_friendly_path(path)
        if not flame_path:
            return

        self.flame.batch.import_clip(flame_path, 'Schematic Reel 1')

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
        self._sg_signout_marker = os.path.join(self.framework.bundle_location, self.framework.name + '.signout')
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

fw = flameAppFramework()
app = menuBatchLoader(fw)
#user = app.get_user()
    
def app_initialized(project_name):
    import flame
    app.flame = flame

def get_batch_custom_ui_actions():
    app.refresh()    
    return app.build_menu()
