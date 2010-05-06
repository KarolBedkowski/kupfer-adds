# -*- coding: UTF-8 -*-
__kupfer_name__ = _("System Services")
__kupfer_sources__ = ("SystemServicesSource", )
__description__ = _("Start, stop or restart system services via init scripts")
__version__ = "0.2"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"

import os
import gtk

from kupfer import plugin_support
from kupfer.objects import Leaf, Action, Source
from kupfer.obj.helplib import FilesystemWatchMixin
from kupfer import utils
from kupfer.core.jsonsettings import JsonExtendedSetting
from kupfer.ui.plugin_conf_dialog import PluginConfDialogController


def _get_services_scripts_location():
	for initd_path in ('/etc/init.d/', '/etc/rc.d/init.d', '/etc/rc.d'):
		if os.path.exists(initd_path) and os.path.isdir(initd_path):
			return initd_path


# skip this services
_SERVICES_BLACK_LIST = [
		"acpid", "acpi-support", "alsa-utils", "apmd", "binfmt-support",
		"bootlogd", "bootmisc.sh", "checkfs.sh", "checkroot.sh",
		"console-screen.kbd.sh", "console-setup", "dbus", "dns-clean", "glibc.sh",
		"hal", "halt", "hostname.sh", "hotkey-setup", "hwclockfirst.sh",
		"hwclock.sh", "keyboard-setup", "killprocs", "klogd", "laptop-mode",
		"linux-restricted-modules-common", "module-init-tools",
		"mountall-bootclean.sh", "mountall.sh", "mountdevsubfs.sh", "mountkernfs.sh",
		"mountnfs-bootclean.sh", "mountnfs.sh", "mountoverflowtmp", "mtab.sh",
		"policykit", "pppd-dns", "procps", "rc", "rc.local", "rcS", "reboot",
		"readahead", "readahead-desktop", "rmnologin", "screen-cleanup", "sendsigs",
		"single", "stop-bootlogd", "stop-bootlogd-single", "stop-readahead",
		"sysklogd", "system-tools-backends", "udev", "udev-finish", "umountfs",
		"umountnfs.sh", "umountroot", "urandom", "vbesave", "wpa-ifupdown", "x11-common",
		'README'
]


class PluginSettings(JsonExtendedSetting):
	''' Configuration - list of serives to show in browser.'''
	_preserve_attr = ('services', )

	def __init__(self, confobj=None):
		self.initd_path = _get_services_scripts_location()
		if confobj:
			self.services = confobj.services
		else:
			# for default show all services
			self.services = list(self._get_services())

	def _get_services(self):
		for filename in os.listdir(self.initd_path):
			if (filename in _SERVICES_BLACK_LIST \
					or filename.find('dpkg-') > 0 or filename.endswith('~') \
					or filename.startswith('.')):
				continue
			file_path = os.path.join(self.initd_path, filename)
			if os.path.isfile(file_path):
				yield filename

	def dialog(self, parent_widget):
		contr = PluginConfDialogController(parent_widget, _("Service list"))
		contr.add_header(_('<span weight="bold" size="larger">'
			'Please select services</span>\n'
			'Selected services will be show in browser.'))
		contr.add_scrolled_wnd(self._create_list())

		for service in self._get_services():
			enabled = service in self.services
			self.store.append((enabled, service))

		res = contr.run()
		if res:
			self.services = [service for enabled, service in self.store if enabled]
		return res

	def _create_list(self):
		self.columns = ("service", "enabled")
		self.store = gtk.ListStore(bool, str)
		table = gtk.TreeView(self.store)
		table.set_search_column(1)

		checkcell = gtk.CellRendererToggle()
		checkcol = gtk.TreeViewColumn("", checkcell)
		checkcol.add_attribute(checkcell, "active", 0)
		checkcell.connect("toggled", self._on_service_toggled)
		table.append_column(checkcol)

		cell = gtk.CellRendererText()
		col = gtk.TreeViewColumn(_("Service"), cell)
		col.add_attribute(cell, "markup", 1)
		table.append_column(col)

		table.show()
		return table

	def _on_service_toggled(self, cell, path):
		it = self.store.get_iter(path)
		enabled = not self.store.get_value(it, 0)
		self.store.set_value(it, 0, enabled)


__kupfer_settings__ = plugin_support.PluginSettings(
	{
		'key': 'sudo_cmd',
		'label': _("Sudo-like Command"),
		'type': str,
		'value': "gksu"
	},
	{
		'key': 'services',
		'label': 'Select services',
		'type': PluginSettings,
		'value': None,
	},
)


class Service(Leaf):
	""" Represent system service """
	def get_actions(self):
		yield StartService()
		yield StopService()
		yield RestartService()

	def get_description(self):
		return self.object

	def get_icon_name(self):
		return "applications-system"


class _ServiceAction(Action):
	def __init__(self, name, icon, command):
		Action.__init__(self, name)
		self._icon = icon
		self._command = command

	def get_icon_name(self):
		return self._icon

	def activate(self, leaf):
		sudo_cmd = __kupfer_settings__["sudo_cmd"]
		utils.spawn_in_terminal([sudo_cmd, leaf.object, self._command])

	def item_types(self):
		yield Service


class StartService(_ServiceAction):
	""" Start service action """
	def __init__(self):
		_ServiceAction.__init__(self, _('Start Service'), 'start', 'start')


class RestartService(_ServiceAction):
	""" restart service action """
	def __init__(self):
		_ServiceAction.__init__(self, _('Restart Service'), 'reload', 'restart')


class StopService(_ServiceAction):
	""" restart service action """
	def __init__(self):
		_ServiceAction.__init__(self, _('Stop Service'), 'stop', 'stop')


class SystemServicesSource(Source, FilesystemWatchMixin):
	''' Index system services from /etc/*/init.d/ '''

	def __init__(self, name=_("System Services")):
		Source.__init__(self, name)

	def is_dynamic(self):
		return True

	def get_items(self):
		if not __kupfer_settings__['services']:
			return

		initd_path = __kupfer_settings__['services'].initd_path
		if not initd_path:
			return

		for service in __kupfer_settings__['services'].services:
			file_path = os.path.join(initd_path, service)
			yield Service(file_path, _("%s Service") % service)

	def should_sort_lexically(self):
		return True

	def get_icon_name(self):
		return "applications-system"

	def provides(self):
		yield Service



