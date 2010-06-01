# -*- coding: UTF-8 -*-
''' GnuPG support functions '''
from __future__ import with_statement

__version__ = "2010-05-28"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


import os
import subprocess
import time

from kupfer import utils
from kupfer.obj.base import Leaf, Action, Source
from kupfer.obj.objects import TextLeaf
from kupfer.obj.helplib import FilesystemWatchMixin


KEYS_PRIVATE = '-K'
KEYS_PUBLIC = '-k'
PGP_HEADER_MSG = '-----BEGIN PGP MESSAGE-----'
PGP_HEADER_SIG = '-----BEGIN PGP SIGNED MESSAGE----'
PGP_HEADER_PUBKEY = '-----BEGIN PGP PUBLIC KEY BLOCK-----'

TRUST_NAMES = {
		"n": _("don't trust"),
		"m": _("marginal"),
		"f": _("fully"),
		"u": _("ultimately"),
		"-": _("unknown"),
}


class Key(Leaf):
	def __init__(self, keyid, owner, trust, expiration):
		Leaf.__init__(self, keyid, owner)
		desc = [_("Id:"), keyid[-8:]] if keyid else []
		if trust:
			desc.extend((_("Trust:"), TRUST_NAMES.get(trust, trust)))
		if expiration and expiration != '-':
			desc.extend((_("Expire:"), expiration))
		self._description = " ".join(desc)

	def get_description(self):
		return self._description

	def get_actions(self):
		yield _GetPublicKey()
		yield _EditKey()

	def get_icon_name(self):
		return "gnome-mime-application-pgp-keys"


class PublicKeysSource(Source, FilesystemWatchMixin):
	_gnupg_home = os.path.expanduser("~/.gnupg/")

	def __init__(self):
		Source.__init__(self, _("GnuPG Public Keyring"))

	def initialize(self):
		self._monitor_token = self.monitor_directories(self._gnupg_home)

	def monitor_include_file(self, gfile):
		return gfile and gfile.get_basename().endswith('.gpg')

	def get_items(self):
		for key, owner, trust, expiration in _get_keys(KEYS_PUBLIC):
			yield Key(key, owner, trust, expiration)

	def should_sort_lexically(self):
		return True


class PrivateKeysSource(Source):
	def __init__(self):
		Source.__init__(self, _("GnuPG Private Keyring"))

	def get_items(self):
		yield Key(None, _("Default Private Key"), None, None)
		for key, owner, trust, expiration in _get_keys(KEYS_PRIVATE):
			yield Key(key, owner, trust, expiration)

	def should_sort_lexically(self):
		return True


class _GetPublicKey(Action):
	def __init__(self):
		Action.__init__(self, _("Export Public Key"))

	def has_result(self):
		return True

	def activate(self, leaf):
		p = subprocess.Popen(["gpg", "--export", "--armor", leaf.object],
			stdout=subprocess.PIPE)
		stdout, _stderr = p.communicate()
		return TextLeaf(stdout)

	def get_description(self):
		return _("Get ASCII armored public key")


class _EditKey(Action):
	def __init__(self):
		Action.__init__(self, _("Edit Key"))

	def activate(self, leaf):
		cli = 'gpg --edit-key %s' % leaf.object
		utils.launch_commandline(cli, 'GnuPG', True)

	def get_description(self):
		return _("Open terminal and edit selected GnuPG key")

#===============


def _get_keys(kind=KEYS_PUBLIC):
	p = subprocess.Popen(["gpg", kind, "--fixed-list-mode", "--with-colons"],
			stdout=subprocess.PIPE)
	stdout, _stderr = p.communicate()
	curr_key = None
	for line in stdout.split('\n'):
		sline = line.split(':')
		rectype = sline[0]
		if rectype in ('pub', 'sec'):
			trust = sline[1]
			capabilities = sline[11]
			curr_key = None
			if trust in ('i', 'r', 'e') or capabilities == 'D':
				# skip invalid, revoked, expired and disabled keys
				continue
			keyid = sline[4]
			expiration = _format_date(sline[6])
			curr_key = (keyid, trust, expiration)
		elif rectype == 'uid':
			if curr_key is None:
				continue
			owner = line.split(':')[9]
			yield curr_key[0], owner, curr_key[1], curr_key[2]


def _format_date(timestamp):
	if not timestamp:
		return '-'
	return time.strftime("%x", time.localtime(int(timestamp)))


def format_recipients_params(recipients):
	for recipient in recipients:
		yield '-r'
		yield recipient
