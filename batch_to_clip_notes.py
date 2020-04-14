import os
import sys
import base64
import uuid
from datetime import datetime

#   ================
#    CONFIGURATION
#   ================

flame_batch_root = '/TCP/flame_archives'
flame_batch_folder = 'flame_batch_setups'

#   ================
#   FLAME BATCH SECTION
#   ================

def batch_setup_root():
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
        except:
            print ('can not create %s' % flame_batch_path)
            return False
    
    return flame_batch_path

def collect_clip_uids(render_dest):
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

def bless_clip(clip, **kwargs):
    batch_setup_name = kwargs.get('batch_setup_name')
    blessing_string = 'BatchSetup: ' + batch_setup_name
    for version in clip.versions:
        for track in version.tracks:
            for segment in track.segments:
                new_comment = segment.comment + blessing_string
                segment.comment = new_comment
                # print ('blessing %s with %s' % (clip.name, blessing_string))
    return True

def bless_batch_renders(userData):
    import flame
    '''
    finds clips that was not in the render destionations before
    abd blesses them by adding batch_setup_name to the comments
    '''

    batch_setup_name = userData.get('batch_setup_name')
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
                                bless_clip(clip, batch_setup_name = batch_setup_name)

        elif dest == 'Batch Shelf Reels':
            batch_shelf_reels_dest = render_dest_uids.get(dest)
            for batch_shelf_reel_name in batch_shelf_reels_dest.keys():
                previous_uids = batch_shelf_reels_dest.get(batch_shelf_reel_name)
                for reel in flame.batch.shelf_reels:
                    if reel.name == batch_shelf_reel_name:
                        for clip in reel.clips:
                            if clip.uid not in previous_uids:
                                bless_clip(clip, batch_setup_name = batch_setup_name)

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
                                    bless_clip(clip, batch_setup_name = batch_setup_name)
                                except:
                                    print ('libraries are protected from editing')
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
                                            bless_clip(clip, batch_setup_name = batch_setup_name)

def create_batch_uid():
    '''
    generates UUID for the batch setup
    '''
    uid = ((str(uuid.uuid1()).replace('-', '')).upper())
    timestamp = (datetime.now()).strftime('%y%m%d%H%M')
    return timestamp + uid[:1]

def batch_render_begin(info, userData, *args, **kwargs):
    import flame
    
    # get uid and make sure there's no batch with the same name
    current_batch_uid = create_batch_uid()
    batch_file_name = flame.batch.name + '_' + current_batch_uid + '.batch'
    while os.path.isfile(batch_file_name):
        current_batch_uid = create_batch_uid()
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

    userData['render_dest_uids'] = collect_clip_uids(render_dest)
    userData['current_batch_uid'] = current_batch_uid

def batch_render_end(info, userData, *args, **kwargs):
    import flame

    flame_batch_path = batch_setup_root()
    current_batch_uid = userData.get('current_batch_uid')
    batch_setup_name = flame.batch.name + '_' + current_batch_uid
    path = os.path.join(flame_batch_path, batch_setup_name)
    if not info.get('aborted'):
        print ('saving batch into %s' % path)
        flame.batch.save_setup(path)
        userData['batch_setup_name'] = batch_setup_name
    else:
        userData['batch_setup_name'] = 'Render aborted by user'

    bless_batch_renders(userData)
