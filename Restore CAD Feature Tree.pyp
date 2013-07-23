# -*- coding: utf-8 -*-
# 
#  Restore CAD Feature Tree.pyp
#  CINEMA 4D Python Plugins
#  
#  Created by André Berg on 2011-03-19.
#  Copyright 2011 Berg Media. All rights reserved.
#
#  Updated: 2013-07-22 (v1.0)
#  
#  Scenario
#
#  Often times when you import "triangulated" models from
#  a CAD package, the hierarchical relationships from the
#  "feature tree" (think C4D's object manager which has a 
#  very similar purpose) get lost in translation. 
#  Like for example in CINEMA 4D you can make paramteric 
#  objects editable and thus loose the ability to edit after 
#  the fact.
#
#  With some CAD packages however, information about these 
#  relationships gets encoded into the name strings of all 
#  exported submodels (called parts in CAD lingo) that comprise 
#  the complete model (the assembly in CAD terms), making it 
#  possible to restore the relationships/nestings and mirror 
#  them in CINEMA 4D's Object Manager. 
#  
#  Modus Operandi
#
#  This Script does just that. It attempts to rebuild the lost 
#  information by parsing the object names of all imported objects. 
#
#  It was primarily made for a workflow from Pro/E (exported as STEP) to 
#  PunchCAD's ViaCAD/SharkFX from which to export as Wavefront OBJ.
#
#  ViaCAD produces excellent quality polygonal OBJ models and it encodes 
#  the relationship from the feature tree found in the STEP file into
#  the model units it writes to the OBJ file.
#  
#  For example, when this OBJ is imported into CINEMA 4D, one object 
#  might be named:
#  
#  A_762_82_001_37_ASM|Next assembly relationship#A_620_45_120_11_OPEN_AF0_ASM|Next assembly relationship#13_BCC_01_001_11_AF0;13_BCC_01_001_11_AF1
#
#  from which a tree structure can be derived:
#
#  A_762_82_001_37_ASM
#   +- A_620_45_120_11_OPEN_AF0_ASM
#       +- 13_BCC_01_001_11_AF0
#       +- 13_BCC_01_001_11_AF1
# 
#  Additionally there's a pre/post filtering system to clean up the 
#  object names before splitting and processing, as well as making 
#  sure there are no duplicates.
#

import os
import sys
import re
import time
import c4d
from c4d import plugins, utils, bitmaps, gui, documents
import ConfigParser

DEBUG = False

if DEBUG:
    import pprint
    pp = pprint.PrettyPrinter(width=200)
    PP = pp.pprint
    PF = pp.pformat

CR_YEAR = time.strftime("%Y")

# -------------------------------------------
#               PLUGING IDS 
# -------------------------------------------

# unique ID
ID_RESTORECADFEATURETREE = 1026859

IDD_DIALOG_MAIN          = 10000
IDC_STATIC_SPLIT_REGEX   = 10001
IDC_EDIT_SPLIT_REGEX     = 10002
IDC_STATIC_NAMEFIXES     = 10003
IDC_EDIT_NAME_FIXES      = 10004
IDC_BUTTON_CANCEL        = 10005
IDC_BUTTON_DOIT          = 10006
IDC_GROUP_WRAPPER        = 20000
IDC_GROUP_SETTINGS       = 20001
IDC_GROUP_BUTTONS        = 20002
IDC_MENU_ABOUT           = 30001

IDS_PLUGIN_VERSION = 1.0
IDS_PLUGIN_NAME = "Restore CAD Feature Tree"
IDS_HELP_STRING = "Restore feature tree relations from imported CAD models by parsing object names"

IDS_BUTTON  = "Do It!"
IDS_BUTTON1 = "Cancel"
IDS_DIALOG  = "Restore CAD Feature Tree"
IDS_STATIC  = "Split Regex"
IDS_STATIC1 = "Settings"
IDS_STATIC2 = "Button Group"
IDS_STATIC3 = "Name Fixes"
IDS_STATIC4 = "Wrapper Group"
IDS_M_INFO  = "Info"
IDS_M_ABOUT = "About..." 

IDS_ABOUT   = """(C) %s Andre Berg (Berg Media)
All rights reserved.

Version %s

Restore CAD Feature Tree is a command plugin that 
helps with restoring "feature tree" relationships 
found in CAD files. It requires the relationship
information to be encoded into the names of the
imported objects.

Use at your own risk! 

It is recommended to try out the plugin 
on a spare copy of your data first.
""" % (CR_YEAR, IDS_PLUGIN_VERSION)


IDS_SETTINGS_PARSE_ERROR_SPLITREGEX_UNKNOWN = "Parsing Split Regex failed. The error message was: %s"
IDS_SETTINGS_PARSE_ERROR_NAMEFIXES_UNKNOWN = "Parsing Name Fixes failed. The error message was: %s"
IDS_SETTINGS_PARSE_ERROR_WRONG_SYNTAX = """Please use the following syntax only: "'searchstring': 'replacement'".\nUse commas to separate multiple pairs."""
IDS_SETTINGS_PARSE_ERROR_BLACKLISTED = "Error: please refrain from using the following words: 'import os', 'removedirs', 'remove', 'rmdir'"

BLACKLIST = ['import os', 'removedirs', 'remove', 'rmdir']

# Defaults
DEFAULT_SPLIT_REGEX = "'\\||;|#'"
DEFAULT_NAME_FIXES = """'Next:assembly:relationship#': '',
':X2:00F6:X0:': 'oe',
':X2:00E4:X0:': 'ae',
':X2:00FC:X0:': 'ue'"""


# ---------------------------------------------------------------------
#                      Helpers and Utilities 
# ---------------------------------------------------------------------

class Helpers(object):
    """Contains helper methods to collaps a few lines into one method call."""
    def __init__(self, arg):
        super(Helpers, self).__init__()
    
    @staticmethod
    def readConfig(filepath=None):
        """Read settings from a configuration file.
            
        Returns None if config file at filepath doesn't exist.
        Returns the config object on success.
        """
        result = None
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res/", "config.ini")
        if os.path.exists(filepath):
            config = ConfigParser.ConfigParser()
            config.read(filepath)
            result = config
        return result
    
    @staticmethod
    def saveConfig(config, filepath=None):
        """Save settings to configuration file.
            
        Returns True if successful, False otherwise.
        """
        result = False
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res/", "config.ini")
        try:
            with open(filepath, 'wb') as configfile:
                config.write(configfile)
            result = True
        except Exception, e:
            print "*** Caught Exception: %r ***" % e
        return result
    
    @staticmethod
    def initConfig(defaults, filepath=None):
        """Initialize configuration file by writing the defaults.
            
        Returns True if config file was created, 
        False if config file already exists or otherwise.
        """
        result = False
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res/", "config.ini")
        if not os.path.exists(filepath):
            config = ConfigParser.ConfigParser(defaults)
            result = Helpers.saveConfig(config, filepath)
        return result
    
    @staticmethod
    def select(op):
        if not op.GetBit(c4d.BIT_ACTIVE):
            op.ToggleBit(c4d.BIT_ACTIVE)
        return op.GetBit(c4d.BIT_ACTIVE)
    
    @staticmethod
    def selectAdd(op):
        """Same as select(op) but uses a slightly different mechanism.
            
        See also BaseDocument.SetSelection(sel, mode).
        """
        doc = op.GetDocument()
        doc.SetActiveObject(op, c4d.SELECTION_ADD)
    
    @staticmethod
    def selectGroup(grp):
        for obj in grp:
            doc = obj.GetDocument()
            # add each group member to the selection 
            # so we can group them in the object manager
            #doc.AddUndo(UNDO_BITS, obj)
            doc.SetActiveObject(obj, c4d.SELECTION_ADD)
    
    @staticmethod
    def selectObjects(objs):
        for op in objs:
            Helpers.select(op)
    
    @staticmethod
    def deselectAll(inObjMngr=False):
        """Not the same as BaseSelect.DeselectAll().
            
        inObjMngr  bool  if True, run the deselect command from Object Manager, 
                         else the general one for editor viewport
        """
        if inObjMngr is True:
            c4d.CallCommand(100004767) # deselect all (Object Manager)
        else:
            c4d.CallCommand(12113) # deselect all
    
    @staticmethod
    def groupC4dObjects(name, objs):
        Helpers.deselectAll(True)
        result = None
        if name is None or objs is None: 
            return result
        if not isinstance(objs, list):
            objs = [objs]
        for o in objs:
            select(o)
        if DEBUG: print "creating group %s" % name
        c4d.CallCommand(100004772) # group objects
        grp = doc.GetActiveObject()
        grp.SetName(name)
        result = grp
        return result
    
    @staticmethod
    def getHNext(op):
        if not op: return
        if op.GetDown(): return op.GetDown()
        while not op.GetNext() and op.GetUp():
            op = op.GetUp()
        return op.GetNext()
    
    @staticmethod
    def getActiveObjects(doc):
        """Same as BaseDocument.GetSelection(), except GetSelection also selects tags and materials."""
        lst = list()
        op = doc.GetFirstObject()
        while op:
            if op.GetBit(c4d.BIT_ACTIVE) == True: 
                lst.append(op)
            op = Helpers.getHNext(op)
        return lst
    
    @staticmethod
    def createObject(typ, name, undo=True):
        obj = None
        try:
            doc = documents.GetActiveDocument()
            obj = c4d.BaseObject(typ)
            doc.InsertObject(obj)
            if undo is True:
                doc.AddUndo(c4d.UNDOTYPE_NEW, obj)
            c4d.EventAdd()
        except Exception, e:
            print "*** Caught Exception: %r ***" % e
        return obj
    
    @staticmethod
    def insertObjectsIntoGroup(objs, grp=None, copy=False):
        if grp is None:
            grp = Helpers.createObject(c4d.Onull, "untitled group")
        if copy == True: 
            objs = [i.GetClone() for i in objs]
        if DEBUG: print "inserting objs into group '%s'" % grp.GetName()
        if isinstance(objs, list):
            [obj.InsertUnder(grp) for obj in objs]
        else:
            objs.InsertUnder(grp)
        c4d.EventAdd()
        return grp
    

# ------------------------------------------------------
#                   Command Script 
# ------------------------------------------------------

class RestoreCADFeatureTreeScript(object):
    """The Python script that get's executed when the user hits the Do It! button."""
    
    def __init__(self, scriptvarsdict):
        super(RestoreCADFeatureTreeScript, self).__init__()
        self.data = scriptvarsdict
    
    def createC4dGroupsByTreeMerging(self, selection, regex):
        """Create C4D groups by using a top-down approach to approximating a feature tree.
            
        The main 'trick' here is a flat dictionary used as a tree, 
        which becomes quasi-nested by use of concatenated path strings.
            
        If we use re-concatenated strings of previously split name parts
        as keys for the tree dict (where the value is a null object as group)
        we only ever have one group for each nested path in a tree if the
        dict weren't flat but had leafs.
        """
        tree = {}   # memoizing flat tree
        grps = []   # all groups
        objs = []   # actual polygon objects that should be grouped
        sep = '|'   # path string separator
        
        sel = selection[:] # copy selection
        for op in sel:
            opname = op.GetName()
            parts = re.split(regex, opname)
            op.SetName(parts[-1])
            objs.append(op)
            pathbits = []
            pathstr = None
            lastpathstr = None
            i = 0
            for part in parts[:-1]:
                pathbits.append(part)
                pathstr = sep.join([str(s) for s in pathbits])
                if not tree.has_key(pathstr):
                    gname = part
                    grp = Helpers.createObject(c4d.Onull, gname)
                    grp.SetName(gname)
                    grps.append(grp)
                    tree[pathstr] = grp
                    if lastpathstr is not None:
                        Helpers.insertObjectsIntoGroup(grp, tree[lastpathstr])
                else:
                    grp = tree[pathstr]
                if DEBUG: 
                    print "pathstr       = %s" % pathstr
                    print "lastpathstr = %s" % lastpathstr
                lastpathstr = pathstr
                i += 1
            try:
                fgrp = tree[pathstr]
                Helpers.insertObjectsIntoGroup(objs, fgrp)
            except Exception, e:
                continue
            objs = []
        Helpers.selectObjects(grps)
        if DEBUG: print "tree = %r" % tree
        return grps
    
    def cleanObjectNamesInSelection(self, doc, sel, map):
        if DEBUG: print "pre-cleaning object names in selection..."
        for obj in sel:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            n = obj.GetName()
            mapi = map.items()
            for k, v in mapi:
                n = re.sub(k, v, n)
            obj.SetName(n)
    
    def run(self):
        try:
            fixes = self.data['namefixes']
            splitregex = self.data['splitregex']
        except KeyError, e:
            print "RestoreCADFeatureTreeScript: invalid state: script vars not found in data."
            return False
        
        doc = documents.GetActiveDocument()
        doc.StartUndo()
        
        sel = doc.GetSelection()
        if sel is None: exit(1)
        
        c4d.StatusSetSpin()
        timestart = c4d.GeGetMilliSeconds()
        
        # stop the press before we modify the scene
        c4d.StopAllThreads()
        
        if DEBUG:
           print "------------- cleaning -------------"
        
        self.cleanObjectNamesInSelection(doc, sel, fixes)
        
        grps = self.createC4dGroupsByTreeMerging(sel, splitregex)
        
        if DEBUG:
            print "------------- grouping -------------"
            print "grps: %r" % grps
        
        c4d.EventAdd()
        c4d.StatusClear()
        
        timeend = int(c4d.GeGetMilliSeconds() - timestart)
        timemsg = "Restore CAD Feature Tree: finished in " + str(timeend) + " milliseconds"
        print timemsg
        
        #c4d.EventAdd()
        doc.EndUndo()
        
        return True
    


# ------------------------------------------------------
#                   User Interface 
# ------------------------------------------------------

class RestoreCADFeatureTreeDialog(gui.GeDialog):
    
    def CreateLayout(self):
        self.SetTitle(IDS_DIALOG)
        
        # Wrapper Group
        self.GroupBegin(IDC_GROUP_WRAPPER, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0, "", 0) #id, flags, cols, rows, title, groupflags
        self.GroupBorder(c4d.BORDER_NONE)
        self.GroupBorderSpace(10, 0, 10, 0)
        
        # Settings Group
        self.GroupBegin(IDC_GROUP_SETTINGS, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 2, 0, IDS_STATIC1, 0) #id, flags, cols, rows, title, groupflags
        self.GroupBorder(c4d.BORDER_GROUP_TOP)
        self.GroupBorderSpace(20, 7, 20, 5)
        self.GroupSpace(4, 4)
        self.AddStaticText(IDC_STATIC_SPLIT_REGEX, c4d.BFH_CENTER | c4d.BFV_CENTER, name=IDS_STATIC) # id, flags[, initw=0][, inith=0][, name=""][, borderstyle=0]
        self.AddMultiLineEditText(IDC_EDIT_SPLIT_REGEX, c4d.BFH_SCALEFIT | c4d.BFV_TOP, initw=374, inith=22, style=c4d.DR_MULTILINE_MONOSPACED | c4d.DR_MULTILINE_SYNTAXCOLOR | c4d.DR_MULTILINE_PYTHON) # id, flags[, initw=0][, inith=0][, style=0]
        
        self.AddStaticText(IDC_STATIC_NAMEFIXES, c4d.BFH_CENTER | c4d.BFV_CENTER, name=IDS_STATIC3) # id, flags[, initw=0][, inith=0][, name=""][, borderstyle=0]
        self.AddMultiLineEditText(IDC_EDIT_NAME_FIXES, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, initw=390, inith=80, style=c4d.DR_MULTILINE_MONOSPACED | c4d.DR_MULTILINE_SYNTAXCOLOR | c4d.DR_MULTILINE_PYTHON | c4d.DR_MULTILINE_STATUSBAR) # id, flags[, initw=0][, inith=0][, style=0]
        
        self.GroupEnd() 
        # Settings Group End
        
        self.AddSeparatorH(inith=360)
        
        # Buttons Group
        self.GroupBegin(IDC_GROUP_BUTTONS, c4d.BFH_CENTER | c4d.BFV_TOP, 2, 0, IDS_STATIC2, 0) #id, flags, cols, rows, title, groupflags
        self.GroupBorderSpace(0, 0, 0, 5)
        self.GroupSpace(4, 4)
        self.AddButton(IDC_BUTTON_CANCEL, c4d.BFH_LEFT | c4d.BFV_TOP, name=IDS_BUTTON1) # id, flags[, initw=0][, inith=0][, name=""]
        self.AddButton(IDC_BUTTON_DOIT, c4d.BFH_LEFT | c4d.BFV_TOP, name=IDS_BUTTON) # id, flags[, initw=0][, inith=0][, name=""]
        self.GroupEnd()
        # Buttons Group End
        
        self.GroupEnd() 
        # Wrapper Group End
        
        # Menu
        self.MenuFlushAll()
        self.MenuSubBegin(IDS_M_INFO)
        self.MenuAddString(IDC_MENU_ABOUT, IDS_M_ABOUT)
        self.MenuSubEnd()
        
        self.MenuFinished()
        
        return True
    
    def InitValues(self):
        config = Helpers.readConfig()
        if config is not None:
            splitregex = config.get("Settings", "splitregex")
            namefixes = config.get("Settings", "namefixes")
            if DEBUG:
                print "stored split regex = %s" % splitregex
                print "stored name fixes = %s" % namefixes
        else:
            splitregex = DEFAULT_SPLIT_REGEX
            namefixes = DEFAULT_NAME_FIXES
            # if the config file isn't there, create it
            config = ConfigParser.ConfigParser()
            config.add_section("Settings")
            config.set("Settings", "splitregex", splitregex)
            config.set("Settings", "namefixes", namefixes)
            Helpers.saveConfig(config)
        self.SetString(IDC_EDIT_SPLIT_REGEX, splitregex)
        self.SetString(IDC_EDIT_NAME_FIXES, namefixes)            
        return True
    
    def Command(self, id, msg):
        curnamefixes = self.GetString(IDC_EDIT_NAME_FIXES)
        cursplitregex = self.GetString(IDC_EDIT_SPLIT_REGEX)
        if id == IDC_BUTTON_DOIT:
            for s in BLACKLIST:
                if s in curnamefixes or s in cursplitregex:
                    c4d.gui.MessageDialog(IDS_SETTINGS_PARSE_ERROR_BLACKLISTED)
                    return False
            if len(curnamefixes) > 0 and not ":" in curnamefixes:
                c4d.gui.MessageDialog(IDS_SETTINGS_PARSE_ERROR_WRONG_SYNTAX)
                return False
            try:
                evalsplitregex = eval("r%s" % cursplitregex)
            except Exception, e:
                c4d.gui.MessageDialog(IDS_SETTINGS_PARSE_ERROR_SPLITREGEX_UNKNOWN % e)
                return False
            try:
                evalnamefixes = eval("{%s}" % curnamefixes)
            except Exception, e:
                c4d.gui.MessageDialog(IDS_SETTINGS_PARSE_ERROR_NAMEFIXES_UNKNOWN % e)
                return False
            scriptvars = {
                'namefixes': evalnamefixes, 
                'splitregex': evalsplitregex
            }
            script = RestoreCADFeatureTreeScript(scriptvars)
            if DEBUG:
                print "do it: %r" % msg
                print "curnamefixes = %r" % curnamefixes
                print "cursplitregex = %r" % cursplitregex
                print "script = %r" % script
                print "scriptvars = %r" % scriptvars
            return script.run()
        elif id == IDC_BUTTON_CANCEL:
            splitregex = self.GetString(IDC_EDIT_SPLIT_REGEX)
            namefixes = self.GetString(IDC_EDIT_NAME_FIXES)
            if DEBUG:
                print "cancel: %r" % msg
                print "curnamefixes = %r" % curnamefixes
                print "cursplitregex = %r" % cursplitregex
            config = Helpers.readConfig()
            if config is not None:
                config.set("Settings", "splitregex", splitregex)
                config.set("Settings", "namefixes", namefixes)
                Helpers.saveConfig(config)
            self.Close()
        elif id == IDC_EDIT_SPLIT_REGEX:
            splitregex = self.GetString(IDC_EDIT_SPLIT_REGEX)
            config = Helpers.readConfig()
            if config is not None:
                config.set("Settings", "splitregex", splitregex)
                Helpers.saveConfig(config)
            if DEBUG:
                print "edit split regex: %r" % msg
                print "curnamefixes = %r" % curnamefixes
                print "cursplitregex = %r" % cursplitregex
                print "splitregex = %s" % splitregex
        elif id == IDC_EDIT_NAME_FIXES:
            namefixes = self.GetString(IDC_EDIT_NAME_FIXES)
            config = Helpers.readConfig()
            if config is not None:
                config.set("Settings", "namefixes", namefixes)
                Helpers.saveConfig(config)
            if DEBUG:
                print "edit name fixes: %r" % msg
                print "curnamefixes = %r" % curnamefixes
                print "cursplitregex = %r" % cursplitregex
                print "namefixes = %s" % namefixes
        elif id == IDC_MENU_ABOUT:
            c4d.gui.MessageDialog(IDS_ABOUT)
        else:
            if DEBUG:
                print "id = %s" % id

        return True

    

# ----------------------------------------------------
#                      Main 
# ----------------------------------------------------

class RestoreCADFeatureTreeMain(plugins.CommandData):
    dialog = None
    def Execute(self, doc):
        # create the dialog
        if self.dialog is None:
            self.dialog = RestoreCADFeatureTreeDialog()
        return self.dialog.Open(c4d.DLG_TYPE_ASYNC, pluginid=ID_RESTORECADFEATURETREE, defaultw=395, defaulth=230)
    
    def RestoreLayout(self, sec_ref):
        # manage nonmodal dialog
        if self.dialog is None:
            self.dialog = RestoreCADFeatureTreeDialog()
        return self.dialog.Restore(pluginid=ID_RESTORECADFEATURETREE, secret=sec_ref)
    


if __name__ == "__main__":
    thispath = os.path.dirname(os.path.abspath(__file__))
    
    icon = bitmaps.BaseBitmap()
    icon.InitWith(os.path.join(thispath, "res/", "icon.tif"))
    
    plugins.RegisterCommandPlugin(
        ID_RESTORECADFEATURETREE, 
        IDS_PLUGIN_NAME, 
        0, 
        icon, 
        IDS_HELP_STRING, 
        RestoreCADFeatureTreeMain()
    )
    
    print "%s v%.1f loaded. (C) %s Andre Berg" % (IDS_PLUGIN_NAME, IDS_PLUGIN_VERSION, CR_YEAR)
