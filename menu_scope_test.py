import os
from sgtk.platform.qt import QtGui

from pprint import pprint, pformat

class menuAction(object):
    def __init__(self):
        self.name = os.path.splitext(os.path.basename(__file__))[0]
        self.mbox = QtGui.QMessageBox()
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('method called with %s' % pformat(args))
            import flame
            message = ''
            for item in args[0]:
                if isinstance(item, flame.PyReel):
                    message += item.name.get_value()
                    message += ' in ' + item.parent.name.get_value() + ', '
            self.mbox.setText(pformat(message))
            self.mbox.exec_()
        return method

    def build_menu(self, number_of_menu_itmes):
        menu = {'name': self.name, 'actions': []}
        for i in xrange(1, number_of_menu_itmes+1):
            menu['actions'].append({
                'name': 'Test selection ' + str(i),
                # 'isVisible': self.scope_reel,
                'execute': getattr(self, 'menu_item_' + str(i))
            })
        return menu
    
    def scope_reel(self, selection):
        import flame
        for item in selection:
            # if isinstance(item, flame.PyReel):
            if isinstance(item, flame.PyReel):
                return True
        return False

    def scope_desktop(self, selection):
        import flame
        for item in selection:
            # if isinstance(item, flame.PyReel):
            if isinstance(item, flame.PyDesktop):
                return True
        return False

app = menuAction()

def get_media_panel_custom_ui_actions():
    return app.build_menu(256)
    '''
    def dummy_action(*args, **kwargs):
        print ('dummy_action called')
        # pprint (args)
        # pprint (kwargs)
    
    menu = {
        'name': 'numerous menu test',
        'actions': []
    }

    number_of_menu_itmes = 256
    for i in xrange(1, number_of_menu_itmes+1):
        menu['actions'].append({
            'name': 'Test selection ' + str(i),
            # 'isVisible': scope_desktop,
            'execute': dummy_action
        })
    return menu
    '''