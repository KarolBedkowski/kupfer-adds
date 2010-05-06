# -*- coding: UTF-8 -*-
from __future__ import with_statement

__kupfer_name__ = _("User Sources")
__kupfer_sources__ = ("UserSourcesSource", )
__description__ = _("User defined sources")
__version__ = "2010-05-12"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


'''
Allow user to define own sources.
Example actions (defined in ~/.config/kupfer/user_sources.cfg'):

[Remind Tasks]
command=rem -s+3 -b1
type=text
dynamic=True

[Test file]
file=~/test.txt
type=text


Fields:
	section: source name
	command: command do execute
	file: text file name to read
	description: optional description for the source
	type: type of the resultat: text, one-text, url, file
	dynamic: is source is dynamic

	Command of file must be defined.
	Each leaf created by given source has set attribute source_name.
'''

import os.path
import subprocess
import ConfigParser

from kupfer import config
from kupfer.obj import objects
from kupfer.obj.base import Source
from kupfer.obj.helplib import FilesystemWatchMixin


CONFIG_FILENAME = 'user_sources.cfg'
RESULT_CLASSES = {
		'url': objects.UrlLeaf,
		'file': objects.FileLeaf,
		'text': objects.TextLeaf,
		'one-text': objects.TextLeaf,
}


class UserSource(Source):
	def __init__(self, name, command, filename):
		Source.__init__(self, name=name)
		self.result_type = 'text'
		self.command = command
		self.filename = os.path.expanduser(filename) if filename else None
		self.dynamic = False
		self.description = _('User Source')

	def repr_key(self):
		return (self.name, self.command, self.filename)

	def is_dynamic(self):
		return self.dynamic

	def get_items(self):
		if self.command:
			itms = self._get_items_from_cmd()
		elif os.path.isfile(self.filename):
			itms = self._get_items_from_file()
		else:
			return
		resclass = RESULT_CLASSES.get(self.result_type, objects.TextLeaf)
		for itm in itms:
			if itm:
				obj = resclass(itm)
				obj.source_name = self.name
				yield obj

	def get_description(self):
		return self.description

	def _get_items_from_cmd(self):
		if self.result_type == 'one-text':
			proc = subprocess.Popen(self.command, shell=True,
					stdout=subprocess.PIPE)
			out, _err = proc.communicate()
			return (out, )

		proc = subprocess.Popen(self.command, shell=True,
				stdout=subprocess.PIPE)
		out, _err = proc.communicate()
		return out.split('\n')

	def _get_items_from_file(self):
		if self.result_type == 'one-text':
			with open(self.filename, 'r') as infile:
				return (infile.read(), )

		with open(self.filename, 'r') as infile:
			return (line.strip() for line in infile.readlines())


_ACTION_DEFAULTS = {
		'command': None,
		'type': None,
		'file': None,
		'dynamic': False,
		'description': None,
}


class UserSourcesSource(Source, FilesystemWatchMixin):
	def __init__(self):
		Source.__init__(self, name=_('User Sources'))

	def initialize(self):
		config_home = config.get_config_paths().next()
		self.monitor_token = self.monitor_directories(config_home)

	def monitor_include_file(self, gfile):
		return gfile and gfile.get_basename() == CONFIG_FILENAME

	def get_items(self):
		_config_file = config.get_config_file('user_sources.cfg')
		if not _config_file or not os.path.isfile(_config_file):
			self.output_debug('no config file')
			return

		self.output_debug('loading sources', _config_file)

		cfgpars = ConfigParser.SafeConfigParser(_ACTION_DEFAULTS)
		cfgpars.read(_config_file)
		for section in cfgpars.sections():
			command = cfgpars.get(section, 'command')
			filename = cfgpars.get(section, 'file')
			if not command and not filename:
				self.output_info('missing command and filename for source:',
						section)
				continue
			src = UserSource(section, command, filename)
			src.result_type = cfgpars.get(section, 'type') or 'text'
			src.description = cfgpars.get(section, 'description')
			src.dynamic = bool(cfgpars.get(section, 'dynamic'))
			yield objects.SourceLeaf(src)
