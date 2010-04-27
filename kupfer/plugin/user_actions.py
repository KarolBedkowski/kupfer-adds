# -*- coding: UTF-8 -*-
from __future__ import with_statement

__kupfer_name__ = _("User Actions")
__kupfer_action_generators__ = ("UserActionsGenerator", )
__description__ = _("User defined actions")
__version__ = "2010-05-05"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


'''
Allow user to define own actions.
Example actions (defined in ~/.config/kupfer/user_actions.cfg'):

[Download with GWget]
objects=url,text
command=gwget $s

[Edit with GIMP]
objects=file
objects_filter=.*(jpg|png)$
command=gimp $s
description=Edit file with GIMP

[Compute MD5sum]
objects=file
command=md5sum $s
gather_result=one-text

[Run by Sudo]
objects=executable
command=gksudo $s


Fields:
	section: action name
	object: name of leaf type (file, text, url, executable, dir)
	objects_filter: optional regex that allow to show action only for selected
		leaves
	command: command do execute; $s is replaces by leaf.object
	description: optional description for the action
	launch_in_terminal: optional, if set launch command in terminal
	gather_result: optional, get result as text|url|file|one-text; default: text
	filters: expression that define what attributes must have leaf to be
		assigned to action. Expression contains parts separated by '|'.
		Each part contains pair of <attribute name>=<value>, separated by '&'.
		Example: filters=source_name=foo&object=12|source_name=bar
		- action is available for object that have source_name = foo and
		  object = 12 or objects that have source_name = bar
'''

import re
import os.path
import subprocess
import ConfigParser

import gtk
import gobject

from kupfer import utils, pretty
from kupfer import config, version
from kupfer import plugin_support
from kupfer.core.settings import ExtendedSetting
from kupfer.obj.base import ActionGenerator, Action, Source
from kupfer.obj import objects


class PluginSettings(ExtendedSetting):
	''' Configuration - list of serives to show in browser.'''
	_preserve_attr = ()

	def __init__(self, confobj=None):
		pass

	def dialog(self, parent_widget):
		self._create_dialog()
		self._curr_action_idx = None
		self.actions = list(load_actions())
		self.fill_actions_combo()
		res = self.dlg.run() == gtk.RESPONSE_ACCEPT
		if res:
			save_actions(self.actions)
		return res

	def _create_dialog(self):
		builder = gtk.Builder()
		builder.set_translation_domain(version.PACKAGE_NAME)
		ui_file = config.get_data_file("user_actions.ui")
		builder.add_from_file(ui_file)
		builder.connect_signals(self)

		self.dlg = builder.get_object("dlg_user_actions")
		self.entry_name = builder.get_object('entry_name')
		self.entry_descr = builder.get_object('entry_descr')
		self.entry_command = builder.get_object('entry_command')
		self.cb_run_in_terminal = builder.get_object('cb_run_in_terminal')
		self.cb_objects = {\
				'text': builder.get_object('cb_obj_text'),
				'url': builder.get_object('cb_obj_url'),
				'file': builder.get_object('cb_obj_file'),
				'executable': builder.get_object('cb_obj_exec'),
				'dir': builder.get_object('cb_obj_dir')}
		self.entry_filter = builder.get_object('entry_filter')
		self.rb_result = {\
				'': builder.get_object('rb_result_none'),
				'text': builder.get_object('rb_result_text'),
				'one-text': builder.get_object('rb_result_onetext'),
				'url': builder.get_object('rb_result_url'),
				'file': builder.get_object('rb_result_file')}
		self.cb_actions = builder.get_object('cb_actions')
		self.btn_del_action = builder.get_object('btn_del_action')

		self.cb_actions_ls = gtk.ListStore(gobject.TYPE_STRING)
		self.cb_actions.set_model(self.cb_actions_ls)
		cell = gtk.CellRendererText()
		self.cb_actions.pack_start(cell, True)
		self.cb_actions.add_attribute(cell, 'text', 0)

	def on_btn_close_pressed(self, widget):
		self.dlg.response(gtk.RESPONSE_CLOSE)
		self.dlg.hide()

	def on_btn_save_pressed(self, widget):
		self.dlg.response(gtk.RESPONSE_ACCEPT)
		self.dlg.hide()

	def on_btn_del_action_pressed(self, widget):
		idx = self.cb_actions.get_active()
		dialog = gtk.MessageDialog(self.dlg,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_QUESTION)
		dialog.set_markup(_('<span weight="bold" size="larger">'
				'Are you sure you want to delete this action?</span>\n\n'
				'All information will be deleted and can not be restored.'))
		dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CLOSE,
				gtk.STOCK_DELETE, gtk.RESPONSE_ACCEPT)
		if dialog.run() == gtk.RESPONSE_ACCEPT:
			self.actions.pop(idx)
			self.cb_actions_ls.remove(self.cb_actions_ls.get_iter(idx))
			if self.actions:
				self.cb_actions.set_active(0)
			self.set_buttons_sensitive()
		dialog.destroy()

	def on_btn_add_action_pressed(self, widget):
		action = UserAction('', '')
		action.name = ''
		self.fill_fields(action)
		self._curr_action_idx = None

	def on_btn_apply_action_pressed(self, widget):
		try:
			self.update_action()
		except RuntimeError, err:
			dlgmsg = gtk.MessageDialog(self.dlg,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_INFO, gtk.BUTTONS_OK)
			dlgmsg.set_markup(_('<span weight="bold" size="larger">'
				'Cannot update action.</span>'))
			dlgmsg.format_secondary_text(str(err))
			dlgmsg.run()
			dlgmsg.hide()

	def on_cb_actions_changed(self, widget):
		idx = widget.get_active()
		if idx < 0:
			return
		action = self.actions[idx]
		self.fill_fields(action)
		self._curr_action_idx = idx

	def fill_fields(self, action):
		self.entry_name.set_text(action.name or '')
		self.entry_descr.set_text(action.description or '')
		self.entry_command.set_text(action.command or '')
		self.entry_filter.set_text(';'.join(action.objects_filter)
				if action.objects_filter else  '')
		if action.leaf_types:
			for type_name, widget in self.cb_objects.iteritems():
				widget.set_active(type_name in action.leaf_types)
		else:
			for type_name, widget in self.cb_objects.iteritems():
				widget.set_active(False)
		result = (action.gather_result or '').strip()
		self.rb_result[result].set_active(True)
		self.cb_run_in_terminal.set_active(action.launch_in_terminal)

	def fill_actions_combo(self):
		self.cb_actions_ls.clear()
		for action in self.actions:
			self.cb_actions_ls.append((action.name, ))
		if self.actions:
			self.cb_actions.set_active(0)
		self.set_buttons_sensitive()

	def update_action(self):
		idx = self._curr_action_idx
		action = UserAction('', '') if idx is None else self.actions[idx]
		actname = self.entry_name.get_text().strip()
		if not actname:
			raise RuntimeError(_('Missing action name'))
		if any(True for act in self.actions if act.name == actname and
				action != act):
			raise RuntimeError(_('Missing action name'))
		action.command = self.entry_command.get_text().strip()
		if not action.command:
			raise RuntimeError(_('Missing command.'))
		action.name = self.entry_name.get_text().strip()
		action.description = self.entry_descr.get_text().strip()
		action.objects_filter = self.entry_filter.get_text().split(';')
		action.leaf_types = []
		for type_name, widget in self.cb_objects.iteritems():
			if widget.get_active():
				action.leaf_types.append(type_name)
		action.gather_result = None
		for result, widget in self.rb_result.iteritems():
			if widget.get_active():
				action.gather_result = result
				break
		action.launch_in_terminal = self.cb_run_in_terminal.get_active()
		if action in self.actions:
			self.cb_actions_ls.set_value(self.cb_actions_ls.get_iter(idx),
					0, action.name)
		else:
			self.actions.append(action)
			self.cb_actions_ls.append((action.name, ))
			self.cb_actions.set_active(len(self.actions) - 1)
		self.set_buttons_sensitive()

	def set_buttons_sensitive(self):
		self.btn_del_action.set_sensitive(len(self.actions) > 0)


__kupfer_settings__ = plugin_support.PluginSettings(
	{
		'key': 'actions',
		'label': 'Configure actions',
		'type': PluginSettings,
		'value': None,
	},
)


class UserAction(Action):
	def __init__(self, name, command):
		Action.__init__(self, name)
		self.command = command
		self.leaf_types = None
		self.description = None
		self.objects_filter = None
		self.launch_in_terminal = False
		self.gather_result = None
		self.filters = []

	def activate(self, leaf):
		cmd = self.command
		if '$s' in cmd:
			try:
				cmd = self.command.replace('$s', leaf.object)
			except TypeError:
				return
		if self.gather_result:
			proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
			out, _err = proc.communicate()
			if self.gather_result == 'url':
				objs = [objects.UrlLeaf(iout) for iout in out.split()]
			elif self.gather_result == 'file':
				objs = [objects.FileLeaf(iout) for iout in out.split()]
			elif self.gather_result == 'one-text':
				objs = (objects.TextLeaf(out), )
			else:
				objs = [objects.TextLeaf(iout) for iout in out.split()]
			return UserActionResultSource(objs)
		else:
			utils.launch_commandline(cmd, self.name, self.launch_in_terminal)

	def is_factory(self):
		return self.gather_result is not None

	def get_description(self):
		return self.description

	def is_valid_for_leaf(self, leaf):
		if self.leaf_types:
			if not self._check_leaf(leaf):
				return False
		if self.objects_filter:
			if not any(re.match(ifilter, leaf.object) for ifilter
					in self.objects_filter):
				return False
		if not self.filters:
			return True
		for filtr in self.filters:
			result = True
			for key, value in filtr.iteritems():
				result = result and getattr(leaf, key, None) == value
			if result:
				return True
		return False

	def _check_leaf(self, leaf):
		if isinstance(leaf, objects.FileLeaf):
			if leaf.is_dir():
				return 'dir' in self.leaf_types
			if leaf._is_executable() and 'executable' in self.leaf_types:
				return True
			return 'file' in self.leaf_types
		if isinstance(leaf, objects.UrlLeaf):
			return 'url' in self.leaf_types
		if isinstance(leaf, objects.TextLeaf):
			return 'text' in self.leaf_types
		# check class name
		leaf_class = leaf.__class__.__name__.split('.')[-1]
		return leaf_class in self.leaf_types


class UserActionResultSource(Source):
	def __init__(self, result):
		Source.__init__(self, name=_("User Action Result"))
		self.result = result

	def get_items(self):
		return self.result


_ACTION_DEFAULTS = {
		'command': None,
		'objects': None,
		'description': None,
		'objects_filter': None,
		'launch_in_terminal': False,
		'gather_result': None,
		'filters': None}


class UserActionsGenerator(ActionGenerator):
	def __init__(self):
		ActionGenerator.__init__(self)
		self._last_loaded_time = 0
		self._config_file = config.get_config_file('user_actions.cfg')
		self._actions = []
		self._load()

	def _load(self):
		if not self._config_file or not os.path.isfile(self._config_file):
			self.output_debug('no config file')
			return []
		config_file_mtime = os.path.getmtime(self._config_file)
		if self._last_loaded_time >= config_file_mtime:
			return self._actions
		self.output_debug('loading actions', self._config_file)
		self._last_loaded_time = config_file_mtime
		self._actions = list(load_actions())
		return self._actions

	def get_actions_for_leaf(self, leaf):
		for action in self._load():
			if action.is_valid_for_leaf(leaf):
				yield action


def load_actions():
	"""docstring for load_actions"""
	config_file = config.get_config_file('user_actions.cfg')
	cfgpars = ConfigParser.SafeConfigParser(_ACTION_DEFAULTS)
	cfgpars.read(config_file)
	for section in cfgpars.sections():
		command = cfgpars.get(section, 'command')
		if not command:
			pretty.print_info('missing command for action:', section)
			continue
		action = UserAction(section, command)
		leaf_types = cfgpars.get(section, 'objects')
		if leaf_types:
			leaf_types = [S.strip() for S in leaf_types.split(',')]
			action.leaf_types = leaf_types
		action.description = cfgpars.get(section, 'description')
		objects_filter = cfgpars.get(section, 'objects_filter')
		if objects_filter:
			action.objects_filter = [S.strip() for S
					in objects_filter.split(';')]
		action.launch_in_terminal = bool(cfgpars.get(section,
				'launch_in_terminal'))
		action.gather_result = cfgpars.get(section, 'gather_result')
		filters = cfgpars.get(section, 'filters')
		if filters:
			action.filters = [dict(fili.split('=', 1)
				for fili in filtr.split('&'))
				for filtr in filters.split('|')]
		yield action


def save_actions(actions):
	cfgpars = ConfigParser.SafeConfigParser()
	for action in actions:
		cfgpars.add_section(action.name)
		if action.leaf_types:
			cfgpars.set(action.name, 'objects', ','.join(action.leaf_types))
		cfgpars.set(action.name, 'command', action.command)
		cfgpars.set(action.name, 'description', action.description or '')
		if action.objects_filter:
			objects_filter = ';'.join(action.objects_filter)
			cfgpars.set(action.name, 'objects_filter', objects_filter)
		cfgpars.set(action.name, 'launch_in_terminal',
				str(action.launch_in_terminal))
		cfgpars.set(action.name, 'gather_result', action.gather_result or '')
		if action.filters:
			filters = '|'.join('&'.join(key + '=' + val for key, val
				in filtetitem.iteritems()) for filtetitem in action.filters)
			cfgpars.set(action.name, 'filters', filters)
	config_file = config.get_config_file('user_actions.cfg')
	with open(config_file, 'wb') as configfile:
		cfgpars.write(configfile)

