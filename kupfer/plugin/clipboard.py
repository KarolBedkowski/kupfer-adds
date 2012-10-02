__kupfer_name__ = _("Clipboards")
__kupfer_sources__ = ("ClipboardSource", )
__kupfer_actions__ = ("ClearClipboards", )
__description__ = _("Recent clipboards and clipboard proxy objects")
__version__ = "2012-06-09"
__author__ = "Ulrik Sverdrup <ulrik.sverdrup@gmail.com>"

import os
from collections import deque

import gio
import gtk

from kupfer.objects import Source, TextLeaf, Action, SourceLeaf
from kupfer.objects import FileLeaf
from kupfer.obj.compose import MultipleLeaf
from kupfer import plugin_support
from kupfer.weaklib import gobject_connect_weakly
from kupfer import kupferstring


__kupfer_settings__ = plugin_support.PluginSettings(
	{
		"key" : "max",
		"label": _("Number of recent clipboards to remember"),
		"type": int,
		"value": 10,
	},
	{
		"key" : "use_selection",
		"label": _("Include selected text in clipboard history"),
		"type": bool,
		"value": False,
	},
	{
		"key" : "sync_selection",
		"label": _("Copy selected text to primary clipboard"),
		"type": bool,
		"value": False,
	},
)

URI_TARGET="text/uri-list"

class SelectedText (TextLeaf):
	qf_id = "selectedtext"
	def __init__(self, text):
		TextLeaf.__init__(self, text, _('Selected Text'))

	def __repr__(self):
		return "<%s %s>" % (__name__, self.qf_id)

class SelectedFile (FileLeaf):
	qf_id = "selectedfile"
	def __init__(self, path):
		FileLeaf.__init__(self, path, _('Selected Directory')
				if os.path.isdir(path) else _('Selected File'))

	def __repr__(self):
		return "<%s %s>" % (__name__, self.qf_id)

class ClipboardText (TextLeaf):
	def get_description(self):
		numlines = self.object.count("\n") + 1
		desc = self.get_first_text_line(self.object)

		return ngettext('Clipboard "%(desc)s"',
			'Clipboard with %(num)d lines "%(desc)s"',
			numlines) % {"num": numlines, "desc": desc }

class ClipboardFile (FileLeaf):
	pass

class CurrentClipboardText (ClipboardText):
	qf_id = "clipboardtext"
	def __init__(self, text):
		ClipboardText.__init__(self, text, _('Clipboard Text'))

	def __repr__(self):
		return "<%s %s>" % (__name__, self.qf_id)

class CurrentClipboardFile (FileLeaf):
	"represents the *unique* current clipboard file"
	qf_id = "clipboardfile"
	def __init__(self, filepath):
		"""@filepath is a filesystem byte string `str`"""
		FileLeaf.__init__(self, filepath, _('Clipboard File'))

	def __repr__(self):
		return "<%s %s>" % (__name__, self.qf_id)

class CurrentClipboardFiles (MultipleLeaf):
	"represents the *unique* current clipboard if there are many files"
	qf_id = "clipboardfile"
	def __init__(self, paths):
		files = [FileLeaf(path) for path in paths]
		MultipleLeaf.__init__(self, files, _("Clipboard Files"))

	def __repr__(self):
		return "<%s %s>" % (__name__, self.qf_id)


class ClearClipboards(Action):
	def __init__(self):
		Action.__init__(self, _("Clear"))

	def activate(self, leaf):
		leaf.object.clear()

	def item_types(self):
		yield SourceLeaf

	def valid_for_item(self, leaf):
		return isinstance(leaf.object, ClipboardSource)

	def get_description(self):
		return _("Remove all recent clipboards")

	def get_icon_name(self):
		return "edit-clear"


class ClipboardSource (Source):
	def __init__(self):
		Source.__init__(self, _("Clipboards"))
		self.clipboards = deque()

	def initialize(self):
		clip = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
		gobject_connect_weakly(clip, "owner-change", self._clipboard_changed)
		clip = gtk.clipboard_get(gtk.gdk.SELECTION_PRIMARY)
		gobject_connect_weakly(clip, "owner-change", self._clipboard_changed)
		self.clipboard_uris = []
		self.clipboard_text = None
		self.selected_text = None

	def finalize(self):
		self.clipboard_uris = []
		self.clipboard_text = None
		self.selected_text = None
		self.mark_for_update()

	def _clipboard_changed(self, clip, event, *args):
		is_selection = (event.selection == gtk.gdk.SELECTION_PRIMARY)

		max_len = __kupfer_settings__["max"]
		# receive clipboard as gtk text
		newtext = kupferstring.tounicode(clip.wait_for_text())

		is_valid = bool(newtext and newtext.strip())
		is_sync_selection = (is_selection and
		                     __kupfer_settings__["sync_selection"])

		if not is_selection or __kupfer_settings__["use_selection"]:
			if is_valid:
				self._add_to_history(newtext, is_selection)

		if is_sync_selection and is_valid:
			gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD).set_text(newtext)

		if is_selection:
			self.selected_text = newtext
		if not is_selection or is_sync_selection:
			self.clipboard_text = newtext
			if clip.wait_is_target_available(URI_TARGET):
				sdata = clip.wait_for_contents(URI_TARGET)
				self.clipboard_uris = list(sdata.get_uris())
			else:
				self.clipboard_uris = []
		self._prune_to_length(max_len)
		self.mark_for_update()

	def _add_to_history(self, cliptext, is_selection):
		if cliptext in self.clipboards:
			self.clipboards.remove(cliptext)
		# if the previous text is a prefix of the new selection, supercede it
		if (is_selection and self.clipboards
				and (cliptext.startswith(self.clipboards[-1])
				or cliptext.endswith(self.clipboards[-1]))):
			self.clipboards.pop()
		self.clipboards.append(cliptext)

	def _prune_to_length(self, max_len):
		while len(self.clipboards) > max_len:
			self.clipboards.popleft()

	def get_items(self):
		# selected text
		if self.selected_text:
			if is_file(self.selected_text):
				yield SelectedFile(os.path.expanduser(self.selected_text))
			else:
				yield SelectedText(self.selected_text)

		# produce the current clipboard files if any
		paths = filter(None,
		        [gio.File(uri=uri).get_path() for uri in self.clipboard_uris])
		if len(paths) == 1:
			yield CurrentClipboardFile(paths[0])
		if len(paths) > 1:
			yield CurrentClipboardFiles(paths)

		# put out the current clipboard text
		if self.clipboard_text and self.clipboard_text != self.selected_text:
			if is_file(self.clipboard_text):
				yield CurrentClipboardFile(self.clipboard_text)
			else:
				yield CurrentClipboardText(self.clipboard_text)
		# put out the clipboard history
		for t in reversed(self.clipboards):
			if t == self.clipboard_text or t == self.selected_text:
				continue
			if is_file(t):
				yield ClipboardFile(os.path.expanduser(t))
			else:
				yield ClipboardText(t)

	def get_description(self):
		return __description__

	def get_icon_name(self):
		return "edit-paste"

	def provides(self):
		yield TextLeaf
		yield FileLeaf
		yield MultipleLeaf

	def clear(self):
		self.clipboards.clear()
		self.mark_for_update()


def is_file(path):
	return os.path.exists(os.path.expanduser(path))
