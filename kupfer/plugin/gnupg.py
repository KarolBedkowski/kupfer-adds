# -*- coding: UTF-8 -*-
__kupfer_name__ = _("GnuPG Core")
__kupfer_sources__ = ("PublicKeysSource", )
__kupfer_actions__ = ("ImportPubKey", "SearchKeys")
__description__ = _("Core GnuPG functions: access to public keyring, "
		"import and export keys")
__version__ = "2010-05-29"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"

import subprocess

from kupfer import uiutils
from kupfer import utils
from kupfer.obj.base import Action
from kupfer.obj.objects import TextLeaf
from kupfer.obj import contacts

import gnupg_support as support


PublicKeysSource = support.PublicKeysSource


class ImportPubKey(Action):
	def __init__(self):
		Action.__init__(self, _("Import Public Key"))

	def activate(self, leaf):
		p = subprocess.Popen(["gpg", "--import"], stdout=subprocess.PIPE,
				stdin=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = p.communicate(leaf.object)
		uiutils.show_notification(_("Import Public Key"), stdout or stderr)

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		return leaf.object.startswith(support.PGP_HEADER_PUBKEY)

	def get_description(self):
		return _("Import key into GnuPG public keyring")


class SearchKeys(Action):
	"""Search keys on default keyserver"""
	def __init__(self):
		Action.__init__(self, _("Search Key on KeyServer"))

	def activate_multiple(self, leaves):
		cli = ['gpg --search-keys']
		cli.extend((contacts.email_from_leaf(leaf) for leaf in leaves))
		utils.launch_commandline(' '.join(cli), 'GnuPG', True)

	def activate(self, leaf):
		self.activate_multiple((leaf, ))

	def item_types(self):
		yield contacts.ContactLeaf

	def valid_for_item(self, leaf):
		return bool(contacts.email_from_leaf(leaf))
