import os
import sys
import inspect
import re

import sgtk
from sgtk.platform.qt import QtGui

from pprint import pprint
from pprint import pformat

#################
# CONFIGURATION #
#################

flame_bug_message = True
builtin_publisher = False
menu_group_name = 'Menu(SG)'
bunlde_location = '/var/tmp'
storage_root = '/Volumes/projects/'
templates = {
        # known tokens are {Sequence},{Shot},{Step},{name},{version},{frame}
        # {name} and {version} will be guessed from the clip name and taken from
        # Batch itertation number as a fallback.
        # EXAMPLE: Batch iteration number is 009.
        # Any of the clips named as "mycomp", "SHOT_001_mycomp", "SHOT_001_mycomp_009", "SHOT_001_mycomp_v009"
        # Would give us "mycomp" as a {name} and 009 as {version}
        # Version number padding are default to 3 at the moment, ### style padding is not yet implemented
        # Publishing into asset will just replace {Shot} fied with asset name
        'flame_render': 'sequences/{Sequence}/{Shot}/{Step}/publish/{Shot}_{name}_v{version}/{Shot}_{name}_v{version}.{frame}.exr',
        'flame_batch': 'sequences/{Sequence}/{Shot}/{Step}/publish/flame_batch/{Shot}_{name}_v{version}.batch',
        'version_name': '{Shot}_{name}_v{version}'
}

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

class menuPublisher(flameShotgunApp):
    def __init__(self, framework):
        flameShotgunApp.__init__(self, framework)
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

    def scope_clip(self, selection):
        selected_clips = []
        visibility = False
        for item in selection:
            if isinstance(item, (self.flame.PyClip)):
                selected_clips.append(item)
                visibility = True
        return visibility

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
            entity = {}
            for task in tasks:
                entity = task.get('entity')
                if entity:
                    if entity.get('name') == batch_name:
                        break
            if entity:
                self.update_loader_list(entity)
            add_menu_list = self.prefs.get(batch_name + '_batch_loader_add')

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
        sg = self.sg_user.create_sg_connection()

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
                [['login', 'is', self.sg_user.login]],
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
        if prefs['show_all']:            
            menu_item['name'] = '~ Show Assigned Only'
        else:
            menu_item['name'] = '~ Show All Tasks'
        
        show_all_entity = {}
        show_all_entity['caller'] = 'flip_assigned_for_entity'
        show_all_entity['id'] = entity_id
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
                menu['actions'].append(menu_item)
                
        return menu

    def publish(self, entity, selection):

        task = entity.get('task')
        task_entity = task.get('entity')
        task_entity_type = task_entity.get('type')
        task_entity_name = task_entity.get('name')
        task_entity_id = task_entity.get('id')
        task_step = task.get('step.Step.code')

        if not builtin_publisher:
            message = ''
            message += 'Built-in publisher is not yet fully implemented. '
            message += 'You can connect it to your current working publising backend. '
            message += 'If you want to try anyway set builtin_publisher to True '
            message += 'in the beginning of the flame-menu-publisher.py file. '
            message += 'Use it on your own risk. '
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        if not os.path.isdir(storage_root):
            message = 'folder "'
            message += storage_root
            message += '" does not exist. Please set correct project root manually in python file'
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        sg = self.sg_user.create_sg_connection()
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
        
        project_root = os.path.join(storage_root, project_folder_name)
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

        # basic name/version detection from clip name
        flame_project_name = self.flame.project.current_project.name
        batch_group_name = self.flame.batch.name.get_value()

        clip_name = selection[0].name.get_value()
        clip_version_number = -1
        if clip_name.startswith(batch_group_name):
            clip_name = clip_name[len(batch_group_name):]

        if clip_name[-1].isdigit():
            match = re.split('(\d+)', clip_name)
            try:
                clip_version_number = int(match[-2])
            except:
                pass

            v_len = len(match[-2])
            clip_name = clip_name[: -v_len ]
        
        if any([clip_name.startswith('_'), clip_name.startswith(' '), clip_name.startswith('.')]):
            clip_name = clip_name[1:]
        if any([clip_name.endswith('_'), clip_name.endswith(' '), clip_name.endswith('.')]):
            clip_name = clip_name[:-1]
        
        # build export path
        if task_entity_type == 'Shot':
            flame_render = templates.get('flame_render')
            flame_render = flame_shot_render.replace('{Shot}', task_entity_name)
            flame_render = flame_shot_render.replace('{name}', clip_name)
            flame_render = flame_shot_render.replace('{Step}', task_step)
            shot = sg.find_one(
                    'Shot',
                    [['id', 'is', task_entity_id]],
                    [
                    'sg_sequence',
                    ]
                )
            sequence = shot.get('sg_sequence')
            if not sequence:
                sequence_name = 'no_sequence'
            else:
                sequence_name = sequence.get('name')
                if not sequence_name:
                    sequence_name = 'no_sequence'
            flame_render = flame_render.replace('{Sequence}', sequence_name)
            pprint (flame_render)

        if flame_shot_render.endswith('.exr'):
            preset_dir = self.flame.PyExporter.get_presets_dir(
                    self.flame.PyExporter.PresetVisibility.Autodesk,
                    self.flame.PyExporter.PresetType.Image_Sequence
                )
            preset_path = os.path.join(preset_dir, 'OpenEXR', 'OpenEXR (16-bit fp PIZ).xml')
        elif flame_shot_render.endswith('.dpx'):
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
        # exporter.export(clip, preset_path, export_dir)       


        # pprint (templates)
        # pprint (entity)
        # pprint (selection)
        # pprint (proj)

        message = 'Built-in publishing backend is in progress. '
        message += 'Have another look at github in a couple of days. '
        message += "If you wish to help with coding you're very welcome! "
        self.mbox.setText(message)
        self.mbox.exec_()

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
        self._framework.rescan()

    def show_bug_message(self, *args, **kwargs):
        if flame_bug_message:
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

fw = flameAppFramework()
app = menuPublisher(fw)
#user = app.get_user()
    
def app_initialized(project_name):
    import flame
    app.flame = flame

def get_media_panel_custom_ui_actions():
    app.refresh()    
    return app.build_menu()
