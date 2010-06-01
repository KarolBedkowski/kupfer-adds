# -*- coding: UTF-8 -*-
__kupfer_name__ = _("GnuPG File")
__kupfer_actions__ = ("SignFile", "EncryptFile", "SignEncryptFile",
		"VerifyFile", "DecryptFile", "EncryptFileSymmetric")
__description__ = _("Encrypt, decrypt, sign and verify files with GnuPG")
__version__ = "2010-05-30"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


import os
import subprocess

from kupfer import uiutils
from kupfer import utils
from kupfer import plugin_support
from kupfer.obj.base import Action
from kupfer.obj.objects import FileLeaf, TextLeaf

import gnupg_support as support


__kupfer_settings__ = plugin_support.PluginSettings(
	{
		"key" : "ask_for_key",
		"label": _("Ask for key when signing files and text"),
		"type": bool,
		"value": False,
	},
	{
		"key": "default_key",
		"label": _("Default private key"),
		"type": str,
		"value": '',
		"tooltip": _("Leave this field blank for use default GnuPG key.")
	}
)


class SignFile(Action):
	def __init__(self):
		name = _("Sign By...") if __kupfer_settings__['ask_for_key'] \
				else _("Sign")
		Action.__init__(self, name)

	def activate(self, leaf, iobj=None):
		key = iobj.object if iobj else __kupfer_settings__['default_key']
		cli = ['gpg', '--detach-sign', '--batch']
		if key:
			cli.append('--local-user')
			cli.append(key)
		cli.append(leaf.object)
		utils.spawn_async(cli)

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object)

	def requires_object(self):
		return __kupfer_settings__['ask_for_key']

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PrivateKeysSource()

	def get_description(self):
		if __kupfer_settings__['ask_for_key']:
			return _("Sign file with selected private key")
		return _("Sign file with default private key")


class EncryptFile(Action):
	def __init__(self):
		Action.__init__(self, _("Encrypt For..."))

	def activate(self, leaf, iobj):
		self.activate_multiple((leaf, ), (iobj, ))

	def activate_multiple(self, objects, iobjects):
		recipients = (iobj.object for iobj in iobjects)
		cli = ['gpg', '--encrypt-files', '--batch']
		cli.extend(support.format_recipients_params(recipients))
		cli.extend(obj.object for obj in objects)
		utils.spawn_async(cli)

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object)

	def requires_object(self):
		return True

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PublicKeysSource()

	def get_description(self):
		return _("Encrypt file for selected recipients")


class SignEncryptFile(Action):
	def __init__(self):
		Action.__init__(self, _("Sign and Encrypt For..."))

	def activate(self, leaf, iobj):
		self.activate_multiple((leaf, ), (iobj, ))

	def activate_multiple(self, objects, iobjects):
		recipients = (iobj.object for iobj in iobjects)
		cli = ['gpg', '--sign', '--encrypt', '--batch']
		cli.extend(support.format_recipients_params(recipients))
		for obj in objects:
			cli_ = cli[:]
			cli_.append(obj.object)
			utils.spawn_async(cli_)

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object)

	def requires_object(self):
		return True

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PublicKeysSource()

	def get_description(self):
		return _("Sign file with default key then encrypt it with selected key")


class VerifyFile(Action):
	def __init__(self):
		Action.__init__(self, _("Verify Signature"))

	def activate(self, leaf):
		cli = ["gpg", "--verify", "--batch", leaf.object]
		p = subprocess.Popen(cli, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = p.communicate()
		uiutils.show_text_result(stdout or stderr, title=_("Verification Result"))

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object) and (leaf.object.endswith('.asc') or \
				leaf.object.endswith('.sig') or leaf.object.endswith('.gpg'))

	def get_description(self):
		return _("Verify signature validity for selected file")


class DecryptFile(Action):
	def __init__(self):
		Action.__init__(self, _("Decrypt"))

	def activate(self, leaf):
		self.activate_multiple((leaf, ))

	def activate_multiple(self, objects):
		cli = ['gpg', '--decrypt-files', '--batch']
		cli.extend(obj.object for obj in objects)
		utils.spawn_async(cli)

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object) and (leaf.object.endswith('.asc') or \
				leaf.object.endswith('.gpg'))

	def get_description(self):
		return _("Decrypt selected file by GnuPG")


class EncryptFileSymmetric(Action):
	def __init__(self):
		Action.__init__(self, _("Encrypt With Symmetric Cipher"))

	def activate(self, leaf):
		cli = ['gpg', '--symmetric', '--batch', leaf.object]
		utils.spawn_async(cli)

	def item_types(self):
		yield FileLeaf

	def valid_for_item(self, leaf):
		return os.path.isfile(leaf.object)

	def get_description(self):
		return _("Encrypt file using only symmetric cypher")
