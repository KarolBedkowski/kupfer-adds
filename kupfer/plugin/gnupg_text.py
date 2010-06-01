# -*- coding: UTF-8 -*-
__kupfer_name__ = _("GnuPG Text")
__kupfer_actions__ = ("SignText", "EncryptText", "SignEncryptText",
		"VerifySignature", "DecryptText", "EncryptTextSymmetric")
__description__ = _("Encrypt, decrypt, sign and verify text with GnuPG")
__version__ = "2010-05-29"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


import subprocess

from kupfer import uiutils
from kupfer import plugin_support
from kupfer import commandexec
from kupfer import task
from kupfer.obj.base import Action
from kupfer.obj.objects import TextLeaf

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
		"tooltip": _("Leave this field blank for use default GnuPG key."),
	}
)


class _GPGTask(task.ThreadTask):
	def __init__(self, cli, stdin, finish_callback):
		task.ThreadTask.__init__(self)
		self.cli = cli
		self.finish_callback = finish_callback
		self.stdin = stdin
		self.resutl = None

	def thread_do(self):
		try:
			p = subprocess.Popen(self.cli, stdout=subprocess.PIPE,
					stdin=subprocess.PIPE, stderr=subprocess.PIPE)
			stdout, stderr = p.communicate(self.stdin)
		except OSError, err:
			stderr = _("Error when running GPG: %s") % str(err)
			stdout = None
		self.result = stdout or stderr

	def thread_finish(self):
		self.finish_callback(self.result)


def _create_gpg_task(cli, stdin, finish_callback):
	ctx = commandexec.DefaultActionExecutionContext()
	async_token = ctx.get_async_token()
	return async_token, _GPGTask(cli, stdin, finish_callback)


class SignText(Action):
	def __init__(self):
		name = _("Sign By...") if __kupfer_settings__['ask_for_key'] \
				else _("Sign")
		Action.__init__(self, name)

	def is_async(self):
		return True

	def activate(self, leaf, iobj=None):
		key = iobj.object if iobj else __kupfer_settings__['default_key']
		cli = ["gpg", "--clearsign", "--batch"]
		if key:
			cli.extend(("--local-user", key))
		self.async_token, task = _create_gpg_task(cli, leaf.object,
				self._finish_callback)
		return task

	def item_types(self):
		yield TextLeaf

	def requires_object(self):
		return __kupfer_settings__['ask_for_key']

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PrivateKeysSource()

	def get_description(self):
		if __kupfer_settings__['ask_for_key']:
			return _("Sign text with selected private key")
		return _("Sign text with default private key")

	def _finish_callback(self, result):
		ctx = commandexec.DefaultActionExecutionContext()
		ctx.register_late_result(self.async_token, TextLeaf(result))


class EncryptText(Action):
	def __init__(self):
		Action.__init__(self, _("Encrypt For..."))

	def is_async(self):
		return True

	def activate(self, leaf, iobj):
		return self.activate_multiple((leaf, ), (iobj, ))

	def activate_multiple(self, objects, iobjects):
		text = list(objects)[0].object
		recipients = (iobj.object for iobj in iobjects)
		cli = ["gpg", "--encrypt", "--armor", "--batch"]
		cli.extend(support.format_recipients_params(recipients))
		self.async_token, task = _create_gpg_task(cli, text, self._finish_callback)
		return task

	def item_types(self):
		yield TextLeaf

	def requires_object(self):
		return True

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PublicKeysSource()

	def get_description(self):
		return _("Encrypt text for selected recipients")

	def _finish_callback(self, result):
		ctx = commandexec.DefaultActionExecutionContext()
		ctx.register_late_result(self.async_token, TextLeaf(result))


class SignEncryptText(Action):
	def __init__(self):
		Action.__init__(self, _("Sign and Encrypt For..."))

	def is_async(self):
		return True

	def activate(self, leaf, iobj):
		return self.activate_multiple((leaf, ), (iobj, ))

	def activate_multiple(self, objects, iobjects):
		text = list(objects)[0].object
		recipients = (iobj.object for iobj in iobjects)
		cli = ["gpg", "--sign", "--encrypt", "--armor", "--batch"]
		cli.extend(support.format_recipients_params(recipients))
		self.async_token, task = _create_gpg_task(cli, text, self._finish_callback)
		return task

	def item_types(self):
		yield TextLeaf

	def requires_object(self):
		return True

	def object_types(self):
		yield support.Key

	def object_source(self, for_item=None):
		return support.PublicKeysSource()

	def get_description(self):
		return _("Sign text by default key and encrypt it for selected recipients")

	def _finish_callback(self, result):
		ctx = commandexec.DefaultActionExecutionContext()
		ctx.register_late_result(self.async_token, TextLeaf(result))


class VerifySignature(Action):
	def __init__(self):
		Action.__init__(self, _("Verify Signature"))

	def activate(self, leaf):
		cli = ["gpg", "--verify", "--batch"]
		p = subprocess.Popen(cli, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
				stderr=subprocess.PIPE)
		stdout, stderr = p.communicate(leaf.object)
		uiutils.show_text_result(stdout or stderr, title=_("Verification Result"))

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		return leaf.object.startswith(support.PGP_HEADER_SIG)

	def get_description(self):
		return _("Verify text signature validity")


class DecryptText(Action):
	def __init__(self):
		Action.__init__(self, _("Decrypt"))

	def is_async(self):
		return True

	def activate(self, leaf):
		cli = ["gpg", "--decrypt", "--batch"]
		self.async_token, task = _create_gpg_task(cli, leaf.object,
				self._finish_callback)
		return task

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		return leaf.object.startswith(support.PGP_HEADER_MSG)

	def get_description(self):
		return _("Decrypt text with GnuPG")

	def _finish_callback(self, result):
		ctx = commandexec.DefaultActionExecutionContext()
		ctx.register_late_result(self.async_token, TextLeaf(result))


class EncryptTextSymmetric(Action):
	def __init__(self):
		Action.__init__(self, _("Encrypt With Symmetric Cipher"))

	def is_async(self):
		return True

	def activate(self, leaf):
		cli = ["gpg", "--symmetric", "--armor", "--batch"]
		self.async_token, task = _create_gpg_task(cli, leaf.object,
				self._finish_callback)
		return task

	def item_types(self):
		yield TextLeaf

	def get_description(self):
		return _("Encrypt text using only symmetric cypher")

	def _finish_callback(self, result):
		ctx = commandexec.DefaultActionExecutionContext()
		ctx.register_late_result(self.async_token, TextLeaf(result))
