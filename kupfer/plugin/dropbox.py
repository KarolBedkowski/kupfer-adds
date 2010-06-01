# -*- coding: UTF-8 -*-
from __future__ import with_statement

__kupfer_name__ = _("Dropbox")
__kupfer_actions__ = ("GetPublicUrl", "LinkToPublicAndGetUrl")
__description__ = _("Dropbox actions")
__version__ = "2010-05-15"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


import os
import socket
import sqlite3
from contextlib import closing

from kupfer.obj.base import Action
from kupfer.obj.objects import FileLeaf, UrlLeaf, TextLeaf
from kupfer.obj.special import ErrorLeaf
from kupfer import pretty

_SOCKET_COMMAND = os.path.expanduser("~/.dropbox/command_socket")
_SOCKET_IFACE = os.path.expanduser("~/.dropbox/iface_socket")
_DROPBOX_CONFIG = os.path.expanduser("~/.dropbox/config.db")


class NoDropboxRunning(RuntimeError):
	pass


class DropboxError(RuntimeError):
	pass


def _get_dropbox_subdir(subdir):
	if not os.path.isfile(_DROPBOX_CONFIG):
		return None
	with closing(sqlite3.connect(_DROPBOX_CONFIG)) as conn:
		with closing(conn.cursor()) as curs:
			home = curs.execute("select value from config "
					"where key='dropbox_path'").fetchone()
			if home:
				full_path = os.path.join(home[0], subdir)
				if os.path.isdir(full_path):
					return full_path
	return None


class _Dropbox(object):
	def __init__(self):
		pass

	def _connect(self):
		self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self._socket.settimeout(3)
		try:
			self._socket.connect(_SOCKET_COMMAND)
		except socket.error, err:
			pretty.print_info(err)
			raise NoDropboxRunning()
		else:
			self._file = self._socket.makefile("r+", 4096)

	def _disconnect(self):
		self._file.close()
		self._socket.close()

	def _readline(self):
		res = self._file.readline().decode("utf").rstrip("\n")
		# print res
		return res

	def _send_command(self, name, args):
		self._file.write(name)
		self._file.write("\n")
		for keyval in args.iteritems():
			self._file.write("\t".join(keyval))
			self._file.write("\n")
		self._file.write("done\n")
		self._file.flush()
		if self._readline() == "ok":
			res = {}
			while True:
				line = self._readline()
				if line == "done":
					break
				key, val = line.split("\t", 1)
				res[key] = val
			return res
		return {}

	@classmethod
	def get_public_url(cls, filepath):
		dbox = cls()
		dbox._connect()
		try:
			res = dbox._send_command('get_public_link', {'path': filepath})
		except Exception, err:
			pretty.print_error(err)
			raise DropboxError(err)
		else:
			if 'link' in res:
				return res['link']
		finally:
			dbox._disconnect()
		return None


class GetPublicUrl(Action):
	''' Get url to file in ~/Dropbox/Public dir '''
	def __init__(self):
		Action.__init__(self, _('Get Url to the File'))
		self._dropbox_public = _get_dropbox_subdir('Public')

	def activate(self, leaf):
		try:
			link = _Dropbox.get_public_url(leaf.object)
		except DropboxError, err:
			return ErrorLeaf(_('Error getting url'), str(err))
		except NoDropboxRunning:
			return ErrorLeaf(_("Running Dropbox not found"),
					_("Please start Dropbox daemon"))
		else:
			if link:
				return UrlLeaf(link, link)
		return ErrorLeaf(_('Unknown Dropbox error...'))

	def has_result(self):
		return True

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, item):
		if not self._dropbox_public:
			return False
		return self._dropbox_public in item.object

	def get_description(self):
		return _('Get ppublic url to the file in Dropbox Public dir')


class LinkToPublicAndGetUrl(Action):
	''' Get url to file in ~/Dropbox/Public dir '''
	def __init__(self):
		Action.__init__(self, _('Create Link In Public and Get Url'))
		self._dropbox_public = _get_dropbox_subdir('Public')

	def activate(self, leaf):
		dest = os.path.join(self._dropbox_public, os.path.basename(leaf.object))
		if os.path.exists(dest):
			if not os.path.samefile(dest, leaf.object):
				return TextLeaf(_("Link to another file already exists"))
		else:
			try:
				os.symlink(leaf.object, dest)
			except IOError, err:
				return ErrorLeaf(_("Error creating link to file"), str(err))
		if os.path.exists(dest):
			try:
				link = _Dropbox.get_public_url(dest)
			except DropboxError, err:
				return ErrorLeaf(_('Error getting url'), str(err))
			except NoDropboxRunning:
				return ErrorLeaf(_("Running Dropbox not found"),
					_("Please start Dropbox daemon"))
			else:
				if link:
					return UrlLeaf(link, link)
		return ErrorLeaf(_('Unknown Dropbox error...'))

	def has_result(self):
		return True

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, item):
		if not self._dropbox_public:
			return False
		return not item.object.startswith(self._dropbox_public)

	def get_description(self):
		return _('Create link to the file in Dropbox/Public and get public URL')
