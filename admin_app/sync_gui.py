from __future__ import print_function

import json
import os

# try glew + gles or sdl2?
os.environ["KIVY_GL_BACKEND"] = "glew" # "angle_sdl2"  # gl, glew, sdl2, angle_sdl2, mock
os.environ["KIVY_GRAPHICS"] = "gles"  # "gles"
# os.environ["KIVY_GL_DEBUG"] = "1"
# os.environ["USE_SDL2"] = "1"
# os.environ["KIVY_WINDOW"] = "pygame"  # "sdl2" "pygame"
# os.environ["KIVY_IMAGE"] = "sdl2"  # img_tex, img_dds, img_sdl2, img_ffpyplayer, img_gif, img_pil

from kivy.config import Config
Config.set('kivy', 'exit_on_escape', '0')
Config.set('graphics', 'multisamples', '0')
Config.set('graphics', 'fbo', 'software')
#Config.set('KIVY_GRAPHICS', 'gles')
# Adjust kivy config to change window look/behavior
# Config.set('graphics','borderless',1)
# Config.set('graphics','resizable',0)
# Config.set('graphics','position','custom')
# Config.set('graphics','left',500)
# Config.set('graphics','top',10)

# Config.set('graphics', 'resizeable', '0')
# Config.set('graphics', 'borderless', '1')


import sys
import re
from os.path import expanduser
import logging
import paramiko
# Deal with issue #12 - No handlers could be found for logger "paramiko.transport"
paramiko.util.log_to_file("ssh.log")
logging.raiseExceptions = False

# paramiko_logger = logging.getLogger('paramiko.transport')
# if not paramiko_logger.handlers:
#    console_handler = logging.StreamHandler()
#    console_handler.setFormatter(
#        logging.Formatter('%(asctime)s | %(levelname)-8s| PARAMIKO: '
#                      '%(lineno)03d@%(module)-10s| %(message)s')
#    )
# paramiko_logger.addHandler(console_handler)

import uuid
import subprocess
import stat

# Make sure this is here so pyinstaller pulls it in
import pydal

from security import Enc

import threading
import time
from datetime import datetime

# from gluon import DAL, Field
# from gluon.validators import *

import kivy

from kivy.app import App
Config.set('graphics', 'multisamples', '0')
from kivy.network.urlrequest import UrlRequest
from kivy.uix.label import Label
from scrolllabel import ScrollLabel
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.config import ConfigParser
from kivy.uix.settings import SettingsWithSidebar
from kivy.uix.settings import SettingString
from kivy.uix.settings import SettingItem
from kivy.uix.button import Button
from kivy.properties import ListProperty
from kivy.logger import Logger
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
kivy.require('1.10.0')

# TODO TODO TODO - [CRITICAL] [Clock       ] Warning, too much iteration done before the next frame. Check your code, or increase the Clock.max_iteration attribute
# Clock.max_iteration = 20
# Window.size = (900, 800)
# Window.borderless = True
APP_FOLDER = None

# Git Repos to pull
GIT_REPOS = {"sysprep_scripts": "https://github.com/operepo/sysprep_scripts.git",
             "ope": "https://github.com/operepo/ope.git",
             "ope_laptop_binaries": "https://github.com/operepo/ope_laptop_binaries.git",
             "ope_server_sync_binaries": "https://github.com/operepo/ope_server_sync_binaries.git",
             }

# Hooks for development

# A boolean that must be set for any development environment variables to be valid
OPE_DEVMODE = "OPE_DEVMODE" in os.environ
OPE_DEVMODE_GIT_BRANCH = False
if OPE_DEVMODE:
  Logger.info("Base: OPE_DEVMODE set, making development assumptions")
  if "OPE_DEVMODE_GIT_OPE" in os.environ:
    Logger.info("Base: Resetting ope repo to " + os.environ["OPE_DEVMODE_GIT_OPE"])
    GIT_REPOS["ope"] = os.environ["OPE_DEVMODE_GIT_OPE"]
  if "OPE_DEVMODE_GIT_BRANCH" in os.environ:
    OPE_DEVMODE_GIT_BRANCH = os.environ["OPE_DEVMODE_GIT_BRANCH"]
    Logger.info("Base: Using alternate branch for ope git pull: " + OPE_DEVMODE_GIT_BRANCH)

else:
  Logger.info("Base: OPE_DEVMODE not set") 

def get_app_folder():
    global Logger, APP_FOLDER
    ret = ""
    # Adjusted to save APP_FOLDER - issue #6 - app_folder not returning the same folder later in the app?
    if APP_FOLDER is None:
        # return the folder this app is running in.
        # Logger.info("Application: get_app_folder called...")
        if getattr(sys, 'frozen', False):
            # Running in pyinstaller bundle
            ret = sys._MEIPASS
            # Logger.info("Application: sys._MEIPASS " + sys._MEIPASS)
            # Adjust to use sys.executable to deal with issue #6 - path different if cwd done
            # ret = os.path.dirname(sys.executable)
            # Logger.info("AppPath: sys.executable " + ret)
        else:
            ret = os.path.dirname(os.path.abspath(__file__))
            # Logger.info("AppPath: __file__ " + ret)
        APP_FOLDER = ret
    else:
        ret = APP_FOLDER
    return ret


# Run as app starts to make sure we save the current app folder
# in response to issue #6
get_app_folder()


def get_home_folder():
    home_path = expanduser("~")
    return home_path


# Manage multiple screens
sm = ScreenManager()
# Keep a reference to the main window
MAIN_WINDOW = None

# Find the base folder to store data in - use the home folder
BASE_FOLDER = os.path.join(get_home_folder(), ".ope")
# Make sure the .ope folder exists
if not os.path.exists(BASE_FOLDER):
    os.makedirs(BASE_FOLDER, 0o770)


# Define how we should migrate database tables
lazy_tables = False
fake_migrate_all = False
fake_migrate = False
migrate = True

# Progress bar used by threaded apps
progress_widget = None


# <editor-fold desc="Markdown Functions">
# Convert markdown code to bbcode tags so they draw properly in labels
def markdown_to_bbcode(s):
    links = {}
    codes = []

    def gather_link(m):
        links[m.group(1)]=m.group(2); return ""

    def replace_link(m):
        return "[url=%s]%s[/url]" % (links[m.group(2) or m.group(1)], m.group(1))

    def gather_code(m):
        codes.append(m.group(3)); return "[code=%d]" % len(codes)

    def replace_code(m):
        return "%s" % codes[int(m.group(1)) - 1]

    def translate(p="%s", g=1):
        def inline(m):
            s = m.group(g)
            s = re.sub(r"(`+)(\s*)(.*?)\2\1", gather_code, s)
            s = re.sub(r"\[(.*?)\]\[(.*?)\]", replace_link, s)
            s = re.sub(r"\[(.*?)\]\((.*?)\)", "[url=\\2]\\1[/url]", s)
            s = re.sub(r"<(https?:\S+)>", "[url=\\1]\\1[/url]", s)
            s = re.sub(r"\B([*_]{2})\b(.+?)\1\B", "[b]\\2[/b]", s)
            s = re.sub(r"\B([*_])\b(.+?)\1\B", "[i]\\2[/i]", s)
            return p % s
        return inline

    s = re.sub(r"(?m)^\[(.*?)]:\s*(\S+).*$", gather_link, s)
    s = re.sub(r"(?m)^    (.*)$", "~[code]\\1[/code]", s)
    s = re.sub(r"(?m)^(\S.*)\n=+\s*$", translate("~[size=24][b]%s[/b][/size]"), s)
    s = re.sub(r"(?m)^(\S.*)\n-+\s*$", translate("~[size=18][b]%s[/b][/size]"), s)
    s = re.sub(r"(?m)^#\s+(.*?)\s*#*$", translate("~[size=24][b]%s[/b][/size]"), s)
    s = re.sub(r"(?m)^##\s+(.*?)\s*#*$", translate("~[size=18][b]%s[/b][/size]"), s)
    s = re.sub(r"(?m)^###\s+(.*?)\s*#*$", translate("~[b]%s[/b]"), s)
    s = re.sub(r"(?m)^####\s+(.*?)\s*#*$", translate("~[b]%s[/b]"), s)
    s = re.sub(r"(?m)^> (.*)$", translate("~[quote]%s[/quote]"), s)
    # s = re.sub(r"(?m)^[-+*]\s+(.*)$", translate("~[list]\n[*]%s\n[/list]"), s)
    # s = re.sub(r"(?m)^\d+\.\s+(.*)$", translate("~[list=1]\n[*]%s\n[/list]"), s)
    s = re.sub(r"(?m)^((?!~).*)$", translate(), s)
    s = re.sub(r"(?m)^~\[", "[", s)
    s = re.sub(r"\[/code]\n\[code(=.*?)?]", "\n", s)
    s = re.sub(r"\[/quote]\n\[quote]", "\n", s)
    s = re.sub(r"\[/list]\n\[list(=1)?]\n", "", s)
    s = re.sub(r"(?m)\[code=(\d+)]", replace_code, s)

    return s
# </editor-fold>


# <editor-fold desc="Kivy screens and controls">
# Main screen
class StartScreen(Screen):
    pass


# Screen with getting starte info
class GettingStartedScreen(Screen):
    pass


class VerifySettingsScreen(Screen):
    pass


class PickAppsScreen(Screen):
    pass


class OnlineModeScreen(Screen):
    pass


class OfflineModeScreen(Screen):
    pass


class OnlineUpdateScreen(Screen):
    pass


class OfflineUpdateScreen(Screen):
    pass


class LoginScreen(Screen):
    def do_login(self, loginText, passwordText):
        Logger.info("Logging in: " + loginText)
        # app = App.get_running_app()
        #
        # app.username = loginText
        # app.password = passwordText
        #
        # self.manager.transition = SlidTransition(direction="left")
        # self.manager.current = "connected"
        #
        # app.config.read(app.get_application_config())
        # app.config.write()

    def reset_form(self):
        self.ids['login'].text = ""
        self.ids['password'].text = ""
    pass


# === Password Box (masked ***) ===
class PasswordLabel(Label):
    pass


# Class to show a password box in the settings area
class SettingPassword(SettingString):
    def _create_popup(self, instance):
        super(SettingPassword, self)._create_popup(instance)
        self.textinput.password = True

    def add_widget(self, widget, *largs):
        if self.content is None:
            super(SettingString, self).add_widget(widget, *largs)
        if isinstance(widget, PasswordLabel):
            return self.content.add_widget(widget, *largs)


# Class to add a button to the settings area
class SettingButton(SettingItem):
    def __init__(self, **kwargs):
        self.register_event_type('on_release')
        buttons = kwargs.pop('buttons')
        super(SettingItem, self).__init__(**kwargs)
        # super(SettingItem, self).__init__(title=kwargs['title'], panel=kwargs['panel'], key=kwargs['key'],
        #                                  section=kwargs['section'])
        for aButton in buttons: # kwargs["buttons"]:
            oButton = Button(text=aButton['title'], font_size='15sp')
            oButton.ID = aButton['id']
            self.add_widget(oButton)
            oButton.bind(on_release=self.On_ButtonPressed)

    def set_value(self, section, key, value):
        # Normally reads the config parser, skip here
        return

    def On_ButtonPressed(self, instance):
        self.panel.settings.dispatch('on_config_change', self.panel.config, self.section, self.key, instance.ID)


# Class for showing the password popup
class PasswordPopup(Popup):
    # Password function that will be called when the pw is set
    pw_func = None
    pass

# </editor-fold>


class MainWindow(BoxLayout):

    def __init__(self, **kwargs):
        super(MainWindow, self).__init__(**kwargs)

    def on_touch_up(self, touch):
        # Logger.info("main.py: MainWindow: {0}".format(touch))
        pass


class SyncOPEApp(App):
    use_kivy_settings = False

    required_apps = ["ope-gateway", "ope-router", "ope-dns", "ope-clamav", "ope-redis", "ope-postgresql" ]
    recommended_apps = ["ope-fog", "ope-canvas", "ope-smc"]
    # In devmode, don't require anything
    if OPE_DEVMODE:
      Logger.info("Base: OPE_DEVMODE set, not requiring any apps")
      recommended_apps.extend(required_apps)
      required_apps = []
    stable_apps = [ "ope-kalite" ]
    beta_apps = ["ope-coco", "ope-freecodecamp", "ope-gcf", "ope-jsbin", "ope-rachel", "ope-seekoff", "ope-elasticsearch", "ope-wamap"]

    def load_current_settings(self):
        global MAIN_WINDOW

        # Make sure we have a key set
        self.ensure_key()

        # TEST
        # self.set_offline_pw("1234")
        # Logger.info("OFFLINE PW: " + self.get_offline_pw())
        # self.set_online_pw("5678")
        # Logger.info("ONLINE PW: " + self.get_online_pw())

    def ensure_key(self):
        # Ensure we have a key
        auth = self.config.getdefault("Server", "auth1", "")
        if auth == "":
            auth = str(uuid.uuid4()).replace('-', '')
            self.config.set("Server", "auth1", auth)
            self.config.write()

    def get_offline_pw(self):
        self.ensure_key()
        key = self.config.getdefault("Server", "auth1", "")
        pw = self.config.getdefault("Server", "auth2", "")
        if pw != "":
            e = Enc(key)
            pw = e.decrypt(pw)
        else:
            pw = "changeme"
        return pw

    def set_offline_pw(self, pw):
        self.ensure_key()
        key = self.config.getdefault("Server", "auth1", "")
        e = Enc(key)
        pw = e.encrypt(str(pw))
        self.config.set("Server", "auth2", pw)
        self.config.write()

    def get_online_pw(self):
        self.ensure_key()
        key = self.config.getdefault("Server", "auth1", "")
        pw = self.config.getdefault("Server", "auth3", "")
        if pw != "":
            e = Enc(key)
            pw = e.decrypt(pw)
        else:
            pw = "changeme"
        return pw

    def set_online_pw(self, pw):
        self.ensure_key()
        key = self.config.getdefault("Server", "auth1", "")
        e = Enc(key)
        pw = e.encrypt(str(pw))
        self.config.set("Server", "auth3", pw)
        self.config.write()

    def build(self):
        global MAIN_WINDOW

        self.icon = 'logo_icon.png'
        self.title = "Open Prison Education"
        self.settings_cls = SettingsWithSidebar
        MAIN_WINDOW = MainWindow()

        # Make sure to load current settings
        self.load_current_settings()

        # Populate data
        self.populate()

        # Add screens for each window we can use
        sm.add_widget(StartScreen(name="start"))
        sm.add_widget(GettingStartedScreen(name="getting_started"))
        sm.add_widget(VerifySettingsScreen(name="verify_settings"))
        sm.add_widget(PickAppsScreen(name="pick_apps"))
        sm.add_widget(OnlineModeScreen(name="online_mode"))
        sm.add_widget(OfflineModeScreen(name="offline_mode"))
        sm.add_widget(LoginScreen(name="login_screen"))
        sm.add_widget(OnlineUpdateScreen(name="online_update"))
        sm.add_widget(OfflineUpdateScreen(name="offline_update"))

        sm.current = "start"
        return sm  # MAIN_WINDOW

    def build_config(self, config):
        # Default settings
        config.setdefaults("Server",
                           {})
        config.setdefaults("Online Settings",
                           {'server_ip': '127.0.0.1',
                            'server_user': 'root',
                            'server_folder': '/ope'})
        config.setdefaults("Offline Settings",
                           {'server_ip': '127.0.0.1',
                            'server_user': 'root',
                            'server_folder': '/ope'})

        # Generate defaults for selected apps
        selected_apps = {}
        # required apps
        for item in SyncOPEApp.required_apps:
            selected_apps[item] = '1'
        # recommended apps
        for item in SyncOPEApp.recommended_apps:
            selected_apps[item] = '1'
        # stable apps
        for item in SyncOPEApp.stable_apps:
            selected_apps[item] = '0'
        # beta apps #11 fixed
        for item in SyncOPEApp.beta_apps:
            selected_apps[item] = '0'

        config.setdefaults("Selected Apps",
                           selected_apps)

        # config.setdefaults("Build Settings",
        #                    {'build_folder': '~',
        #                     })
        # config.setdefaults("Transfer Settings", {})
        #
        # config.setdefaults("Development Settings", {})
        #
        # config.setdefaults("Production Settings", {})

    def build_settings(self, settings):
        # Register custom settings type
        settings.register_type('password', SettingPassword)
        settings.register_type('button', SettingButton)

        cwd = get_app_folder()
        settings.add_json_panel('Online Settings', self.config,
                                os.path.join(cwd, 'OnlineServerSettings.json'))
        settings.add_json_panel('Offline Settings', self.config,
                                os.path.join(cwd, 'OfflineServerSettings.json'))

        # Don't show this in settings AND in selected apps screen
        # settings.add_json_panel('Selected Apps', self.config, 'SelectedApps.json')

        # settings.add_json_panel('Source Settings', self.config, 'BuildSettings.json')
        # settings.add_json_panel('Transfer Settings', self.config, 'TransferSettings.json')
        # settings.add_json_panel('Development Settings', self.config, 'DevelopmentSettings.json')
        # settings.add_json_panel('Production Settings', self.config, 'ProductionSettings.json')

    def on_config_change(self, config, section, key, value):
        Logger.info("App.on_config_change: {0}, {1}, {2}, {3}".format(config, section, key, value))

        # If this is the password, save it
        if section == "Online Settings" and key == "server_password" and value == "btn_set_password":
            Logger.info("Saving online pw" + value)
            p = PasswordPopup()
            p.pw_func = self.set_online_pw
            p.open()
        if section == "Offline Settings" and key == "server_password" and value == "btn_set_password":
            Logger.info("Saving offline pw" + value)
            p = PasswordPopup()
            p.pw_func = self.set_offline_pw
            p.open()

        # Make sure the settings are stored in global variables
        self.load_current_settings()

    def close_settings(self, settings=None):
        # Settings panel closed
        Logger.info("App.close_settings: {0}".format(settings))
        super(SyncOPEApp, self).close_settings(settings)

    def log_message(self, msg):
        global MAIN_WINDOW

        # Log message to the log area on screen
        MAIN_WINDOW.ids.log_console.text += "\n" + msg
        # Scroll to the bottom
        MAIN_WINDOW.ids.log_console.scroll_y = 0

    def click_entry(self, item_id):
        Logger.info("App.click_entry {0}".format(item_id))

    def populate(self):
        global MAIN_WINDOW
        # Refresh data from database

    def pick_apps(self):
        # Show the screen to select apps to choose
        Logger.info("App.click_pick_apps")
        pass

    def get_file(self, fname):
        # Load the specified file
        ret = ""
        try:
            f = open(fname, "r")
            ret = f.read()
            f.close()
        except:
            # On failure just return ""
            pass
        # Convert git markdown to bbcode tags
        ret = markdown_to_bbcode(ret)
        return ret

    def copy_callback(self, transferred, total):
        global progress_widget
        if progress_widget is None:
            return
        # Logger.info("XFerred: " + str(transferred) + "/" + str(total))
        if total == 0:
            progress_widget.value = 0
        else:
            val = int(float(transferred) / float(total) * 100)
            if val < 0:
                val = 0
            if val > 100:
                val = 100
            if val != progress_widget.value:
                progress_widget.value = val

    def sftp_pull_files(self, remote_path, local_path, sftp, status_label, depth=1):
        # Recursive Walk through the folder and pull changed files
        depth_str = " " * depth
        # TODO - follow symlinks for folders/files
        for f in sftp.listdir_attr(remote_path):
            if stat.S_ISDIR(f.st_mode):
                #status_label.text += "\n" + depth_str + "Found Dir: " + f.filename
                n_remote_path = os.path.join(remote_path, f.filename).replace("\\", "/")
                n_local_path = os.path.join(local_path, f.filename)
                self.sftp_pull_files(n_remote_path, n_local_path, sftp, status_label, depth+1)
            elif stat.S_ISREG(f.st_mode):
                status_label.text += "\n" + depth_str + "Found File: " + os.path.abspath(f.filename)
                # Try to copy it to the local folder
                try:
                    # Make sure the local folder exists
                    os.makedirs(local_path)
                except:
                    # Error if it exits, ignore
                    pass

                r_file = os.path.join(remote_path, f.filename).replace("\\", "/")
                l_file = os.path.join(local_path, f.filename)

                # Get the local modified time of the file
                l_mtime = 0
                try:
                    l_stat = os.stat(l_file)
                    l_mtime = int(l_stat.st_mtime)
                except:
                    # If there is an error, go with a 0 for local mtime
                    pass
                if f.st_mtime == l_mtime:
                    status_label.text += "\n" + depth_str + "Files the same - skipping: " + f.filename
                elif f.st_mtime > l_mtime:
                    status_label.text += "\n" + depth_str + "Remote file newer, downloading: " + f.filename
                    sftp.get(r_file, l_file, callback=self.copy_callback)
                    os.utime(l_file, (f.st_mtime, f.st_mtime))
                else:
                    status_label.text += "\n" + depth_str + "local file newer, skipping: " + f.filename

            else:
                # Non regular file
                status_label.text += "\n" + depth_str + "NonReg File - skipping: " + f.filename

    def sftp_push_files(self, remote_path, local_path, sftp, status_label, depth=1):
        # Recursive Walk through the folder and push changed files
        depth_str = " " * depth

        # Need to decode unicode/mbcs encoded paths
        enc_local_path = local_path.decode(sys.getfilesystemencoding())

        for item in os.listdir(local_path):
            enc_item = item
            try:
                enc_item = item.decode(sys.getfilesystemencoding())
            except:
                # Set it first, then try to decode it, if decode fails use it as is
                pass
            l_path = os.path.join(enc_local_path, enc_item)
            if os.path.isdir(l_path):
                #status_label.text += "\n" + depth_str + "Found Dir: " + enc_item.encode('ascii', 'ignore')
                n_remote_path = os.path.join(remote_path, enc_item).replace("\\", "/")
                n_local_path = os.path.join(enc_local_path, enc_item)
                # Make sure the directory exists on the remote system
                sftp.chdir(remote_path)
                try:
                    sftp.mkdir(enc_item)
                except:
                    # Will fail if directory already exists
                    pass
                self.sftp_push_files(n_remote_path, n_local_path, sftp, status_label, depth+1)
            elif os.path.isfile(l_path):
                status_label.text += "\n" + depth_str + "Found File: " + enc_item.encode('ascii', 'ignore')
                # Try to copy it to the remote folder

                r_file = os.path.join(remote_path, enc_item).replace("\\", "/")
                l_file = os.path.join(enc_local_path, enc_item)

                # Get the local modified time of the file
                l_mtime = 0
                try:
                    l_stat = os.stat(l_file)
                    l_mtime = int(l_stat.st_mtime)
                except:
                    # If there is an error, go with a 0 for local mtime
                    pass
                r_mtime = -1
                try:
                    # Get the stats for the remote file
                    stats = sftp.stat(r_file)
                    r_mtime = stats.st_mtime
                except:
                    pass
                if r_mtime == l_mtime:
                    status_label.text += " - Files the same - skipping. "
                elif l_mtime > r_mtime:
                    status_label.text += " - Local file newer, uploading..."
                    sftp.put(l_file, r_file, callback=self.copy_callback)
                    sftp.utime(r_file, (l_mtime, l_mtime))
                else:
                    status_label.text += " - Remote file newer, skipping. "

            else:
                # Non regular file
                status_label.text += "\n" + depth_str + "NonReg File - skipping: " + enc_item.encode('ascii', 'ignore')

    def sync_volume(self, volume, folder, ssh, ssh_folder, status_label, branch="master"):
        # Sync files on the online server with the USB drive

        # Get project folder (parent folder)
        root_path = os.path.dirname(get_app_folder())
        volumes_path = os.path.join(root_path, "volumes")
        volume_path = os.path.join(volumes_path, volume)
        folder_path = os.path.join(volume_path, folder.replace("/", os.sep))

        # Figure the path for the git app
        git_path = os.path.join(root_path, "bin/bin/git.exe")

        # Ensure the folder exists on the USB drive
        try:
            os.makedirs(folder_path)
        except:
            # will error if folder already exists
            pass

        # Ensure the folder exists on the server
        remote_folder_path = os.path.join(ssh_folder, "volumes", volume, folder).replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("mkdir -p " + remote_folder_path, get_pty=True)
        stdin.close()
        for line in stdout:
            status_label.text += line
            # make sure to read all lines, even if we don't print them
            pass

        status_label.text += "\n[b]Syncing Volume: [/b]" + volume + "/" + folder
        sftp = ssh.open_sftp()

        # Copy remote files to the USB drive
        status_label.text += "\nDownloading new files..."
        self.sftp_pull_files(remote_folder_path, folder_path, sftp, status_label)

        # Walk the local folder and see if there are files that don't exist that should be copied
        status_label.text += "\nUploading new files..."
        self.sftp_push_files(remote_folder_path, folder_path, sftp, status_label)

        sftp.close()

    def git_pull_local(self, status_label, branch="master"):
        global GIT_REPOS, OPE_DEVMODE_GIT_BRANCH, Logger
        ret = ""

        repos = GIT_REPOS

        # Pull each repo into a repo sub folder
        root_path = os.path.dirname(get_app_folder())
        repo_path = os.path.join(root_path, "volumes/repos")
        git_path = os.path.join(root_path, "bin/bin/git.exe")

        # os.chdir(root_path)

        # Make sure the folder exists
        if not os.path.isdir(repo_path) is True:
            # Doesn't exist, create it
            os.makedirs(repo_path)

        for repo in repos:
            repo_branch = branch
            status_label.text += "Pulling " + repo + " (may take several minutes)...\n"
            print("Pulling " + repo)
            # Make sure the repo folder exists
            f_path = os.path.join(repo_path, repo) + ".git"
            if not os.path.isdir(f_path) is True:
                os.mkdir(f_path)
            # Make sure git init is run
            # os.chdir(f_path)

            print("-- Init")
            proc = subprocess.Popen(git_path + " init --bare", cwd=f_path, stdout=subprocess.PIPE)
            proc.wait()
            # ret += proc.stdout.read().decode('utf-8')

            # Make sure we have proper remote settings
            print("-- Remove Remote")
            proc = subprocess.Popen(git_path + " remote remove ope_origin", cwd=f_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.wait()
            # ret += proc.stdout.read().decode('utf-8')
            print("-- Add Remote")
            if OPE_DEVMODE_GIT_BRANCH and repo == "ope":
              Logger.info("Base: Using alternate branch for ope remote: " + OPE_DEVMODE_GIT_BRANCH)
              repo_branch = OPE_DEVMODE_GIT_BRANCH
            proc = subprocess.Popen(git_path + " remote add ope_origin " + repos[repo], cwd=f_path, stdout=subprocess.PIPE)
            proc.wait()
            # ret += proc.stdout.read().decode('utf-8')

            # Set fetch settings to pull all heads
            # print("-- config...")
            # proc = subprocess.Popen(git_path + " config remote.origin.fetch 'refs/heads/*:refs/heads/*' ", cwd=f_path, stdout=subprocess.PIPE)
            # proc.wait()
            # ret += proc.stdout.read().decode('utf-8')

            # Make sure we have the current stuff from github
            # +refs/heads/*:refs/heads/*
            print("-- Fetch")
            cmd = git_path + " --bare fetch -f ope_origin " + repo_branch + ":master"
            proc = subprocess.Popen(cmd, cwd=f_path, bufsize=1, universal_newlines=True, stdout=subprocess.PIPE)
            # out = proc.communicate()[0]
            # print ("--- " + out)
            # for line in proc.stdout.readline():
            # for line in proc.stdout:
            #    print("--- " + str(line))
            proc.wait()
            #    status_label.text += line.decode('utf-8')
            #    Logger.info(line.decode('utf-8'))
            # ret += proc.stdout.read()

        status_label.text += "Done pulling repos"
        return ret

    def git_push_repo(self, ssh, ssh_server, ssh_user, ssh_pass, ssh_folder, status_label, online=True, branch="master", ):
        global GIT_REPOS
        ret = ""

        repos = GIT_REPOS

        remote_name = "ope_online"
        if online is not True:
            remote_name = "ope_offline"

        # Pull each repo into a repo sub folder
        root_path = os.path.dirname(get_app_folder())
        repo_path = os.path.join(root_path, "volumes/repos")
        git_path = os.path.join(root_path, "bin/bin/git.exe")

        # os.chdir(root_path)

        # Make sure the folder exists
        if not os.path.isdir(repo_path) is True:
            # Doesn't exist, create it
            os.makedirs(repo_path)

        # Ensure the base folder exists (e.g. /ope) and is ready for git commands
        stdin, stdout, stderr = ssh.exec_command("mkdir -p " + ssh_folder + "; cd " + ssh_folder + "; git init;", get_pty=True)
        stdin.close()
        for line in stdout:
            # status_label.text += line
            pass

        for repo in repos:
            status_label.text += "Pushing " + repo + " (may take several minutes)...\n"
            print("Pushing " + repo)
            # Make sure the repo folder exists
            f_path = os.path.join(repo_path, repo) + ".git"
            if not os.path.isdir(f_path) is True:
                os.mkdir(f_path)

            # os.chdir(f_path)

            # Ensure the folder exists, is a repo, and has a sub folder (volumes/smc/???.git) that is a bare repo
            remote_repo_folder = os.path.join(ssh_folder, "volumes/smc/git/" + repo + ".git").replace("\\", "/")
            ret += "\n\n[b]Ensuring git repo " + repo + " setup properly...[/b]\n"
            print("-- Init")
            stdin, stdout, stderr = ssh.exec_command("mkdir -p " + remote_repo_folder + "; cd " + remote_repo_folder + "; git init --bare; ", get_pty=True)
            stdin.close()
            for line in stdout:
                # status_label.text += line
                # make sure to read all lines, even if we don't print them
                pass

            # Remove existing remote - in case it is old/wrong
            print("-- Remove Remote")
            proc = subprocess.Popen(git_path + " remote remove " + repo + "_" + remote_name, cwd=f_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.wait()
            # for line in proc.stdout:
            #    status_label.text += line

            # Add current remote address
            print("-- Add Remote")
            proc = subprocess.Popen(git_path + " remote add " + repo + "_" + remote_name + " ssh://" + ssh_user + "@" + ssh_server + ":" + remote_repo_folder, cwd=f_path, stdout=subprocess.PIPE)
            proc.wait()
            # for line in proc.stdout:
            #    status_label.text += line

            # Push to the remote server
            print("-- Push")
            proc = subprocess.Popen(git_path + " push -f " + repo + "_" + remote_name + " " + branch, cwd=f_path, stdout=subprocess.PIPE)
            proc.wait()
            # for line in proc.stdout:
            #    # status_label.text += line
            #    Logger.info(line)

        # Repos are in place, now make sure to checkout the main ope project in the
        # folder on the server (e.g. cd /ope; git pull local_bare origin)

        # Ensure that local changes are stash/saved so that the pull works later
        stdin, stdout, stderr = ssh.exec_command("cd " + ssh_folder + "; git stash;", get_pty=True)
        stdin.close()
        for line in stdout:
            # status_label.text += line
            # make sure to read all lines, even if we don't print them
            pass

        # Have remote server checkout from the bare repo
        stdin, stdout, stderr = ssh.exec_command("cd " + ssh_folder + "; git remote remove local_bare;", get_pty=True)
        stdin.close()
        for line in stdout:
            # status_label.text += line
            # Logger.info(line)
            # make sure to read all lines, even if we don't print them
            pass

        ope_local_bare = os.path.join(ssh_folder, "volumes/smc/git/ope.git").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("cd " + ssh_folder + "; git remote add local_bare " + ope_local_bare + ";", get_pty=True)
        stdin.close()
        for line in stdout:
            # status_label.text += line
            # Logger.info(line)
            # make sure to read all lines, even if we don't print them
            pass

        stdin, stdout, stderr = ssh.exec_command("cd " + ssh_folder + "; git fetch -f local_bare " + branch + ";", get_pty=True)
        stdin.close()
        # The above returns before the operation is done, causing issues with the reset. Wait
        # until done.
        for line in stdout:
            # status_label.text += line
            # Logger.info(line)
            print("---- " + line)
            pass
        #
        # During development, the local repo might end up a later rev than the desired update. Force the local gitrepo
        # to match the last fetch.
        stdin, stdout, stderr = ssh.exec_command("cd " + ssh_folder + "; git reset --hard refs/remotes/local_bare/master;", get_pty=True)
        stdin.close()
        for line in stdout:
            print("---- " + line)
        #   # status_label.text += line
        #    Logger.info(line)
            # Make sure to read stdout and let this process finish
            pass

        status_label.text += "Done pulling repos to USB drive"
        return ret

    def get_enabled_apps(self):
        # Return a list of enabled apps

        # Start with required apps
        enabled_apps = SyncOPEApp.required_apps[:]

        # Check recommended apps
        for item in SyncOPEApp.recommended_apps:
            if self.config.getdefault("Selected Apps", item, "1") == "1":
                enabled_apps.append(item)

        # Check stable apps
        for item in SyncOPEApp.stable_apps:
            if self.config.getdefault("Selected Apps", item, "0") == "1":
                enabled_apps.append(item)
        # Check beta apps
        for item in SyncOPEApp.beta_apps:
            if self.config.getdefault("Selected Apps", item, "0") == "1":
                enabled_apps.append(item)

        return enabled_apps

    def enable_apps(self, ssh, ssh_folder, status_label):
        ret = ""
        # Get the list of enabled apps
        apps = self.get_enabled_apps()

        # Clear all the enabled files
        stdin, stdout, stderr = ssh.exec_command("rm -f " + ssh_folder + "/docker_build_files/ope-*/.enabled", get_pty=True)
        stdin.close()
        r = stdout.read()
        if len(r) > 0:
            status_label.text += "\n" + r.decode('utf-8')

        for a in apps:
            status_label.text += "\n-- Enabling App: " + a
            app_path = os.path.join(ssh_folder, "docker_build_files", a)
            enabled_file = os.path.join(app_path, ".enabled")
            enable_cmd = "mkdir -p " + app_path + "; touch " + enabled_file
            stdin, stdout, stderr = ssh.exec_command(enable_cmd.replace('\\', '/'), get_pty=True)
            stdin.close()
            r = stdout.read()
            if len(r) > 0:
                status_label.text += "\n" + r.decode('utf-8')
        status_label.text += "...."
        return ret

    def generate_local_ssh_key(self, status_label):
        # Get project folder (parent folder)
        root_path = os.path.dirname(get_app_folder())
        # Make sure ssh keys exist (saved in home directory in .ssh folder on current computer)
        bash_path = os.path.join(root_path, "bin/bin/bash.exe")
        # Run this to generate keys
        proc = subprocess.Popen(bash_path + " -c 'if [ ! -f ~/.ssh/id_rsa ]; then ssh-keygen -P \"\" -t rsa -f ~/.ssh/id_rsa; fi'", stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        try:
            # proc.stdin.write("\n\n")  #  Write 2 line feeds to add empty passphrase
            pass
        except:
            # This will fail if it isn't waiting for input, that is ok
            pass
        proc.stdin.close()
        for line in proc.stdout:
            status_label.text += line
        #  ret += proc.stdout.read().decode('utf-8')

    def add_ssh_key_to_authorized_keys(self, ssh, status_label):
        ret = ""

        # Get project folder (parent folder)
        root_path = os.path.dirname(get_app_folder())
        # Make sure ssh keys exist (saved in home directory in .ssh folder on current computer)
        bash_path = os.path.join(root_path, "bin/bin/bash.exe")

        # Make sure remote server has .ssh folder
        stdin, stdout, stderr = ssh.exec_command("mkdir -p ~/.ssh; chmod 700 ~/.ssh;", get_pty=True)
        stdin.close()
        for line in stdout:
            status_label.text += line
            pass

        # Find the server home folder
        stdin, stdout, stderr = ssh.exec_command("cd ~; pwd;", get_pty=True)
        stdin.close()
        server_home_dir = stdout.read().decode('utf-8')
        if server_home_dir is None:
            server_home_dir = ""
        server_home_dir = server_home_dir.strip()

        # Add ssh keys to server for easy push/pull later
        # bash -- cygpath -w ~   to get win version of home directory path
        proc = subprocess.Popen(bash_path + " -c 'cygpath -w ~'", stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        proc.stdin.close()
        home_folder = proc.stdout.read().decode('utf-8').strip()
        # home_folder = get_home_folder() #  expanduser("~")
        rsa_pub_path = os.path.join(home_folder, ".ssh", "id_rsa.pub")
        sftp = ssh.open_sftp()
        sftp.put(rsa_pub_path, os.path.join(server_home_dir, ".ssh/id_rsa.pub.ope").replace("\\", "/"))
        sftp.close()
        # Make sure we remove old entries
        stdin, stdout, stderr = ssh.exec_command("awk '{print $3}' ~/.ssh/id_rsa.pub.ope", get_pty=True)
        stdin.close()
        remove_host = stdout.read().decode('utf-8')
        # Add if/then to command to prevent error when authorized_keys file doesn't exist
        stdin, stdout, stderr = ssh.exec_command("if [ -f ~/.ssh/authorized_keys ]; then sed -i '/" + remove_host.strip() + "/d' ~/.ssh/authorized_keys; fi", get_pty=True)
        stdin.close()
        for line in stdout:
            status_label.text += line
            pass

        # Add id_rsa.pub.ope to the authorized_keys file
        stdin, stdout, stderr = ssh.exec_command("cat ~/.ssh/id_rsa.pub.ope >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys;", get_pty=True)
        stdin.close()
        for line in stdout:
            status_label.text += line
            pass

        # Last step - make sure that servers key is accepted here so we don't get warnings
        known_hosts_path = os.path.join(home_folder, ".ssh", "known_hosts" )
        ssh.save_host_keys(known_hosts_path)

        return ret

    def pull_docker_images(self, ssh, ssh_folder,  status_label, ip, domain, ssh_pass):
        # Run on the online server - pull the current docker images
        ret = ""

        # Need to re-run the rebuild_compose.py file
        build_path = os.path.join(ssh_folder, "docker_build_files").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; echo \"" + ip + "\" > .ip; ", get_pty=True)
        for line in stdout:
            pass
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; if [ ! -f .domain ]; then echo \"" + domain + "\" > .domain; fi ", get_pty=True)
        for line in stdout:
            pass
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; echo \"" + ssh_pass + "\" > .pw; ", get_pty=True)
        for line in stdout:
            pass

        rebuild_path = os.path.join(ssh_folder, "build_tools", "rebuild_compose.py").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("python " + rebuild_path + " auto", get_pty=True)
        try:
            # Write a couple enters in case this is the first time the script is run
            stdin.write("\n\n")
        except:
            pass
        stdin.close()
        for line in stdout:
            status_label.text += line
            pass

        # Run the rebuild
        status_label.text += "Pulling docker apps...\n"
        docker_files_path = os.path.join(ssh_folder, "docker_build_files").replace("\\", "/")
        for app in self.get_enabled_apps():
            status_label.text += "- Pulling " + app + "...\n"
            stdin, stdout, stderr = ssh.exec_command("cd " + docker_files_path + "; docker-compose pull " + app + ";", get_pty=True)
            stdin.close()
            for line in stdout:
                # status_label.text += line
                # Logger.info(line)
                pass

        return ret

    def save_docker_images(self, ssh, ssh_folder, status_label):
        # Dump docker images to the app_images folder on the server
        ret = ""

        # Run the script that is on the server
        save_script = os.path.join(ssh_folder, "sync_tools", "export_docker_images.py").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("python " + save_script, get_pty=True)
        stdin.close()
        for line in stdout:
            status_label.text += line

        return ret

    def load_docker_images(self, ssh, ssh_folder, status_label):
        # Dump docker images to the app_images folder on the server
        ret = ""

        load_script = os.path.join(ssh_folder, "sync_tools", "import_docker_images.py").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("python " + load_script, get_pty=True)
        stdin.close()
        for line in stdout:
            # status_label.text += line.decode('utf-8')
            #status_label.text += "."
            pass

        return ret

    def start_apps(self, ssh, ssh_folder, ssh_pass, status_label, ip, domain):
        # Start the docker apps by calling the up.sh script
        ret = ""

        build_path = os.path.join(ssh_folder, "docker_build_files").replace("\\", "/")

        # Make sure .ip and .domain and .pw files exist
        # CHANGE - when logging in from the sync app, always set the IP to the current ip used to login
        # stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; if [ ! -f .ip ]; then echo \"" + ip + "\" > .ip; fi ", get_pty=True)
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; echo \"" + ip + "\" > .ip; ", get_pty=True)
        for line in stdout:
            pass
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; if [ ! -f .domain ]; then echo \"" + domain + "\" > .domain; fi ", get_pty=True)
        for line in stdout:
            pass
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; echo \"" + ssh_pass + "\" > .pw; ", get_pty=True)
        for line in stdout:
            pass

        # Run twice - sometimes compose fails, so we just rerun it
        # Add auto param to up.sh - to prevent it from asking questions
        stdin, stdout, stderr = ssh.exec_command("cd " + build_path + "; sh up.sh auto; sleep 5; sh up.sh ", get_pty=True)
        stdin.close()
        for line in stdout.read():
            # status_label.text += str(line)
            # print("- " + str(line), end='')
            pass

        return ret

    def copy_docker_images_to_usb_drive(self, ssh, ssh_folder, status_label, progress_bar):
        global progress_widget

        progress_widget = progress_bar

        # Copy images from online server to usb drive
        ret = ""

        # Ensure the local app_images folder exists
        try:
            os.makedirs(os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images"))
        except:
            # Throws an error if already exists
            pass

        # Use the list of enabled images
        apps = self.get_enabled_apps()

        sftp = ssh.open_sftp()

        # Check each app to see if we need to copy it
        for app in apps:
            progress_bar.value = 0
            # Download the server digest file
            online_digest = "."
            current_digest = "..."
            remote_digest_file = os.path.join(ssh_folder, "volumes", "app_images", app + ".digest").replace("\\", "/")
            local_digest_file = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".digest.online")
            current_digest_file = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".digest")
            remote_image = os.path.join(ssh_folder, "volumes", "app_images", app + ".tar.gz").replace("\\", "/")
            local_image = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".tar.gz")
            sftp.get(remote_digest_file, local_digest_file)

            # Read the online digest info
            try:
                f = open(local_digest_file, "r")
                online_digest = f.read().strip()
                f.close()
            except:
                # Unable to read the local digest, just pass
                pass

            # Read the current digest info
            try:
                f = open(current_digest_file, "r")
                current_digest = f.read().strip()
                f.close()
            except:
                # Unable to read the local digest, just pass
                pass

            # If digest files don't match, copy the file to the local folder
            if online_digest != current_digest:
                status_label.text += "\nCopying App: " + app
                sftp.get(remote_image, local_image, callback=self.copy_docker_images_to_usb_drive_progress_callback)
                # Logger.info("Moving on...")
                # Store the current digest
                try:
                    f = open(current_digest_file, "w")
                    f.write(online_digest)
                    f.close()
                except:
                    status_label.text += "Error saving current digest: " + current_digest_file
            else:
                status_label.text += "\nApp hasn't changed, skipping: " + app
            #

        sftp.close()
        return ret

    def copy_docker_images_to_usb_drive_progress_callback(self, transferred, total):
        global progress_widget

        # Logger.info("XFerred: " + str(transferred) + "/" + str(total))
        if total == 0:
            progress_widget.value = 0
        else:
            progress_widget.value = int(float(transferred) / float(total) * 100)

    def copy_docker_images_from_usb_drive(self, ssh, ssh_folder, status_label, progress_bar):
        global progress_widget

        progress_widget = progress_bar

        # Copy images from usb drive to the offline server
        ret = ""

        # Ensure the local app_images folder exists
        try:
            os.makedirs(os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images"))
        except:
            # Throws an error if already exists
            pass

        # Ensure that server has app_images folder
        app_images_path = os.path.join(ssh_folder, "volumes", "app_images").replace("\\", "/")
        stdin, stdout, stderr = ssh.exec_command("mkdir -p " + app_images_path, get_pty=True)
        stdin.close()
        ret += stdout.read().decode('utf-8')

        # Use the list of enabled images
        apps = self.get_enabled_apps()

        sftp = ssh.open_sftp()

        # Check each app to see if we need to copy it
        for app in apps:
            # TODO - Copying every time?
            progress_bar.value = 0
            # Download the server digest file
            offline_digest = "."
            current_digest = "..."
            remote_digest_file = os.path.join(ssh_folder, "volumes", "app_images", app + ".digest").replace("\\", "/")
            local_digest_file = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".digest.offline")
            current_digest_file = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".digest")
            remote_image = os.path.join(ssh_folder, "volumes", "app_images", app + ".tar.gz").replace("\\", "/")
            local_image = os.path.join(os.path.dirname(get_app_folder()), "volumes", "app_images", app + ".tar.gz")

            # Make sure to remove the local digest file - keeps us from assuming it has been copied during edge cases
            if os.path.isfile(local_digest_file):
                os.unlink(local_digest_file)

            try:
                sftp.get(remote_digest_file, local_digest_file)
            except:
                # If we can't get this file, its ok, just assume we need to copy
                pass

            # Read the online digest info
            try:
                f = open(local_digest_file, "r")
                offline_digest = f.read().strip()
                f.close()
            except:
                # Unable to read the local digest, just pass
                pass

            # Read the current digest info
            try:
                f = open(current_digest_file, "r")
                current_digest = f.read().strip()
                f.close()
            except:
                # Unable to read the local digest, just pass
                pass

            # If digest files don't match, copy the file to the local folder
            if offline_digest != current_digest:
                status_label.text += "\nCopying App: " + app
                try:
                    sftp.put(local_image, remote_image, callback=self.copy_docker_images_from_usb_drive_progress_callback)
                except:
                    status_label.text += "\n       [b][color=ff0000]Error[/color][/b] pushing " + local_image + "  -- make sure you have pulled it properly by running the Online Sync first."
                    continue
                # Logger.info("Moving on...")
                # Store the current digest
                try:
                    f = open(local_digest_file, "w")
                    f.write(current_digest)
                    f.close()
                except:
                    status_label.text += "Error saving current digest: " + current_digest_file
                # Copy digest file to server
                try:
                    sftp.put(local_digest_file, remote_digest_file)
                except:
                    status_label += "Error pushing digest file to server:  " + local_digest_file
            else:
                status_label.text += "\nApp hasn't changed, skipping: " + app
            #

        sftp.close()
        return ret

    def copy_docker_images_from_usb_drive_progress_callback(self, transferred, total):
        global progress_widget
        if progress_widget is None:
            return

        # Logger.info("XFerred: " + str(transferred) + "/" + str(total))
        if total == 0:
            progress_widget.value = 0
        else:
            progress_widget.value = int(float(transferred) / float(total) * 100)

    def sync_volumes(self, ssh, ssh_folder, status_label):
        # Sync volumes of offline OR online server to USB drive
        # TODO - check enabled apps first

        apps = self.get_enabled_apps()
        for app in apps:
            if app == "ope-canvas":
                # Sync canvas files (student and curriculum files)
                # self.sync_volume('canvas', 'tmp/files', ssh, ssh_folder, status_label)
                # - sync canvas db (sync db dumps)
                # self.sync_volume('canvas', 'db/sync', ssh, ssh_folder, status_label)

                # TODO - rebuild canvas assets
                # docker exec -it ope-canvas bash -c "$GEM_HOME/bin/bundle exec rake canvas:compile_assets"
                pass

            if app == "ope-smc":
                # Sync SMC movies
                # self.sync_volume('smc', 'media', ssh, ssh_folder, status_label)
                # TODO - trigger movie import
                pass

            if app == "ope-fog":
                # Sync FOG images
                # self.sync_volume('fog', 'share_images', ssh, ssh_folder, status_label)
                # TODO - trigger image import
                pass

            if app == "ope-postgresql":
                # Dump data so we can import/sync/merge it
                cmd = "docker-compose exec ope-postgresql bash -c 'mkdir -p /db_backup/canvas/canvas_production'"
                cmd = "docker-compose exec ope-postgresql bash -c 'pg_dump -d canvas_production -U postgres -f /db_backup/canvas/canvas_production -F d --data-only --blobs --disable-triggers --quote-all-identifiers'"

                # self.sync_volume('postgresql', 'canvas', ssh, ssh_folder, status_label)
                pass


    def update_online_server(self, status_label, run_button=None, progress_bar=None):
        if run_button is not None:
            run_button.disabled = True
        # Start a thread to do the work
        status_label.text = "[b]Starting Update[/b]..."
        threading.Thread(target=self.update_online_server_worker, args=(status_label, run_button, progress_bar)).start()

    def update_online_server_worker(self, status_label, run_button=None, progress_bar=None):
        global progress_widget
        progress_widget = progress_bar

        # Get project folder (parent folder)
        root_path = os.path.dirname(get_app_folder())

        # Pull current stuff from GIT repo so we have the latest code
        status_label.text += "\n\n[b]Git Pull[/b]\nPulling latest updates from github...\n"
        status_label.text += self.git_pull_local(status_label)

        # Login to the OPE server
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        domain = "ed"
        ssh_server = self.config.getdefault("Online Settings", "server_ip", "127.0.0.1")
        ssh_user = self.config.getdefault("Online Settings", "server_user", "root")
        ssh_pass = self.get_online_pw()  # self.config.getdefault("Online Settings", "server_password", "")
        ssh_folder = self.config.getdefault("Online Settings", "server_folder", "/ope")
        status_label.text += "\n\n[b]Connecting to Docker server[/b]\n " + ssh_user + "@" + ssh_server + "..."

        try:
            # Connect to the server
            ssh.connect(ssh_server, username=ssh_user, password=ssh_pass, compress=True)

            # Make sure we have an SSH key to use for logins
            self.generate_local_ssh_key(status_label)

            # Add our ssh key to the servers list of authorized keys
            self.add_ssh_key_to_authorized_keys(ssh, status_label)

            # Push local git repo to server - should auto login now
            status_label.text += "\n\n[b]Pushing repo to server[/b]\n"
            self.git_push_repo(ssh, ssh_server, ssh_user, ssh_pass, ssh_folder, status_label, online=True)
            progress_bar.value = 0

            # Set enabled files for apps
            status_label.text += "\n\n[b]Enabling apps[/b]\n"
            self.enable_apps(ssh, ssh_folder, status_label)

            # Download the current docker images
            status_label.text += "\n\n[b]Downloading current apps[/b]\n - downloading around 10Gig the first time...\n"
            self.pull_docker_images(ssh, ssh_folder, status_label, ssh_server, domain, ssh_pass)
            progress_bar.value = 0

            # Run the up command so the docker apps start
            status_label.text += "\n\n[b]Starting Apps[/b]\n - some apps may be slow to come online (e.g. canvas)...\n"
            self.start_apps(ssh, ssh_folder, ssh_pass, status_label, ssh_server, domain)

            # Save the image binary files for syncing
            status_label.text += "\n\n[b]Zipping Docker Apps[/b]\n - will take a few minutes...\n"
            self.save_docker_images(ssh, ssh_folder, status_label)
            progress_bar.value = 0

            # Download docker images to the USB drive
            status_label.text += "\n\n[b]Copying Docker Apps to USB drive[/b]\n - will take a few minutes...\n"
            self.copy_docker_images_to_usb_drive(ssh, ssh_folder, status_label, progress_bar)
            progress_bar.value = 0

            # Start syncing volume folders
            status_label.text += "\n\n[b]Syncing Volumes[/b]\n - may take a while...\n"
            self.sync_volumes(ssh, ssh_folder, status_label)

            ssh.close()
        except paramiko.ssh_exception.BadHostKeyException:
            print("Invalid Host key!")
            status_label.text += "\n\n[b]CONNECTION ERROR[/b]\n - Bad host key - check ~/.ssh/known_hosts"
            if run_button is not None:
                run_button.disabled = False
            return False
        except Exception as ex:
            status_label.text += "\n\n[b]SYNC ERROR[/b]\n - Unable to complete sync "
            if 'Bad authentication type' in ex:
                status_label.text += "\n[b]INVALID LOGIN[/b]"
            status_label.text += "\n\n[b]Exiting early!!![/b]"
            if run_button is not None:
                run_button.disabled = False
            return False
            # Logger.info("Error connecting: " + str(ex))

        status_label.text += "\n\n[b]DONE[/b]"
        if run_button is not None:
            run_button.disabled = False

        pass

    def update_offline_server(self, status_label, run_button=None, progress_bar=None):
        if run_button is not None:
            run_button.disabled = True
        # Start a thread to do the work
        status_label.text = "[b]Starting Update[/b]..."
        threading.Thread(target=self.update_offline_server_worker, args=(status_label, run_button, progress_bar)).start()

    def update_offline_server_worker(self, status_label, run_button=None, progress_bar=None):
        global progress_widget
        progress_widget = progress_bar

        # Get project folder (parent folder)
        root_path = os.path.dirname(get_app_folder())

        # Login to the OPE server
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        domain = "ed"
        ssh_server = self.config.getdefault("Offline Settings", "server_ip", "127.0.0.1")
        ssh_user = self.config.getdefault("Offline Settings", "server_user", "root")
        ssh_pass = self.get_offline_pw()  # self.config.getdefault("Offline Settings", "server_password", "")
        ssh_folder = self.config.getdefault("Offline Settings", "server_folder", "/ope")
        status_label.text += "\n\n[b]Connecting to Docker server[/b]\n " + ssh_user + "@" + ssh_server + "..."

        try:
            # Connect to the server
            ssh.connect(ssh_server, username=ssh_user, password=ssh_pass, compress=True, look_for_keys=False)

            # Make sure we have an SSH key to use for logins
            self.generate_local_ssh_key(status_label)

            # Add our ssh key to the servers list of authorized keys
            self.add_ssh_key_to_authorized_keys(ssh, status_label)

            # Push local git repo to server - should auto login now
            status_label.text += "\n\n[b]Pushing repo to server[/b]\n"
            self.git_push_repo(ssh, ssh_server, ssh_user, ssh_pass, ssh_folder, status_label, online=False)
            progress_bar.value = 0

            # Set enabled files for apps
            status_label.text += "\n\n[b]Enabling Docker Apps[/b]\n"
            self.enable_apps(ssh, ssh_folder, status_label)

            # Copy images from USB to server
            status_label.text += "\n\n[b]Copying Docker Apps from USB drive[/b]\n - will take a few minutes...\n"
            self.copy_docker_images_from_usb_drive(ssh, ssh_folder, status_label, progress_bar)

            # Import the images into docker
            status_label.text += "\n\n[b]UnZipping Docker Apps[/b]\n - may take several minutes...\n"
            self.load_docker_images(ssh, ssh_folder, status_label)
            progress_bar.value = 0

            # Run the up command so the docker apps start
            status_label.text += "\n\n[b]Starting Docker Apps[/b]\n - some apps may be slow to come online (e.g. canvas)...\n"
            self.start_apps(ssh, ssh_folder, ssh_pass, status_label, ssh_server, domain)

            # Start syncing volume folders
            status_label.text += "\n\n[b]Syncing Volumes[/b]\n - may take a while...\n"
            self.sync_volumes(ssh, ssh_folder, status_label)

            ssh.close()
        except paramiko.ssh_exception.BadHostKeyException:
            print("Invalid Host key!")
            status_label.text += "\n\n[b]CONNECTION ERROR[/b]\n - Bad host key - check ~/.ssh/known_hosts"
            if run_button is not None:
                run_button.disabled = False
            return False
        except Exception as ex:
            status_label.text += "\n\n[b]SYNC ERROR[/b]\n - Unable to complete sync: "
            if 'Bad authentication type' in str(ex):
                status_label.text += "\n[b]INVALID LOGIN[/b]"
            status_label.text += "\n\n[b]Exiting early!!![/b]"
            if run_button is not None:
                run_button.disabled = False
            return False
            # Logger.info("Error connecting: " + str(ex))

        status_label.text += "\n\n[b]DONE[/b]"
        if run_button is not None:
            run_button.disabled = False

        pass

    def verify_ope_server(self, status_label):
        # See if you can connect to the OPE serve and if the .ope_root file is present
        status_label.text += "starting..."
        threading.Thread(target=self.verify_ope_server_worker, args=(status_label,)).start()

    def verify_ope_server_worker(self, status_label):
        ssh_server = self.config.getdefault("Online Settings", "server_ip", "127.0.0.1")
        ssh_user = self.config.getdefault("Online Settings", "server_user", "root")
        ssh_pass = self.config.getdefault("Online Settings", "server_password", "")
        ssh_folder = self.config.getdefault("Online Settings", "server_folder", "/ope")

        status_label.text = "Checking connection..."

        try:
            ssh.connect(ssh_server, username=ssh_user, password=ssh_pass, compress=True, look_for_keys=False)
            stdin, stdout, stderr = ssh.exec_command("ls -lah " + ssh_folder + " | grep .ope_root | wc -l ", get_pty=True)
            stdin.close()
            count = stdout.read().decode('utf-8').strip()
            if count == "1":
                status_label.text += "\n\nFound OPE folder - you are ready to go."
            else:
                status_label.text += "\n\nERROR - Connection succeeded, but OPE folder not found. "
                Logger.info("1 means found root: " + str(count))

            ssh.close()
        except paramiko.ssh_exception.BadHostKeyException:
            print("Invalid Host key!")
            status_label.text += "\n\n[b]CONNECTION ERROR[/b]\n - Bad host key - check ~/.ssh/known_hosts"
            return False
        except Exception as ex:
            status_label.text += "\n\nERROR - Unable to connect to OPE server : " + str(ex)
            Logger.info("Error connecting: " + str(ex))

        # status_label.text += " done."

    def close_app(self):
        App.get_running_app().stop()

    def set_app_active(self, app_name, value):
        # Save the status of the app
        ret = value

        # Always return true for required apps (can't turn them off)
        if app_name in SyncOPEApp.required_apps:
            ret = "1"

        if ret is False:
            ret = "0"
        if ret is True:
            ret = "1"

        Logger.info("Setting app: " + app_name + " " + str(ret))
        self.config.set("Selected Apps", app_name, ret)
        self.config.write()
        return ret

    def is_app_active(self, app_name):
        ret = self.config.getdefault("Selected Apps", app_name, "0")

        # Always return true for required apps
        if app_name in SyncOPEApp.required_apps:
            ret = "1"

        return ret

    def is_app_disabled(self, app_name):
        return app_name in SyncOPEApp.required_apps

    def show_settings_panel(self, panel_name):
        # Make sure settings are visible
        self.open_settings()

        # Try to find this panel
        content = self._app_settings.children[0].content
        menu = self._app_settings.children[0].menu

        curr_p = content.current_panel
        for p in content.panels:
            val = content.panels[p]
            if val.title == panel_name:
                curr_p = val

        # Set selected item
        content.current_uid = curr_p.uid
        # Show selected item in the menu
        # TODO - This manually finds the button, should be able to bind properly
        for button in menu.buttons_layout.children:
            if button.uid != curr_p.uid:
                button.selected = False
            else:
                button.selected = True
        # Bind the current_uid property to the menu
        # content.bind(current_uid=menu.on_selected_uid)
        # menu.bind(selected_uid=self._app_settings.children[0].content.current_uid)
        # content.current_uid = curr_p.uid
        # menu.selected_uid = self._app_settings.children[0].content.current_uid


if __name__ == "__main__":
    # Start the app
    SyncOPEApp().run()


# === Build process ===

# = ClamAV =
# Standard docker build - just enable and do typical build/up

# === Sync to USB process ===
# = ClamAV =
# TODO - Have clam av sync to get new virus patterns from internet
# run this on build server:  docker exec -it ope-clamav /dl_virus_defs.sh
# 1 way sync from volumes folder - build -> USB


# === Sync to development process ===

# = ClamAV =
# 1 way sync from volumes folder - USB -> Server

# === Sync to production process ===
# Same as sync development process just point to a different server
