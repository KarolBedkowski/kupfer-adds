__kupfer_name__ = _("Timestamp")
__kupfer_actions__ = ("Convert", "ConvertToTimestamp")
__description__ = _("Convert timestamp to the human readable format")
__version__ = "2010-05-29"
__author__ = "Jan Krajdl <spm@spamik.cz>"

import time

from kupfer import plugin_support
from kupfer import kupferstring
from kupfer.objects import Action, TextLeaf


_FORMATS = {
		_("Locale's appropriate date and time representation"): "%c",
		"dd.MM.yyyy hh:mm:ss": "%d.%m.%Y %H:%M:%S",
		"MM/dd/yyyy hh:mm:ss": "%m/%d/%Y %H:%M:%S",
		"yyyy/MM/dd hh:mm:ss": "%Y/%m/%d %H:%M:%S",
}

__kupfer_settings__ = plugin_support.PluginSettings(
	{
		"key": "date_format",
		"label": _("Output format"),
		"type": str,
		"value": _("Locale's appropriate date and time representation"),
		"alternatives": _FORMATS.keys(),
	},
)


def _try_to_convert_text_to_date(text):
	text = kupferstring.tolocale(text)
	for format_ in _FORMATS.itervalues():
		try:
			value = time.strptime(text, format_)
		except ValueError:
			pass
		else:
			return value
	return None


class Convert(Action):
	def __init__(self):
		Action.__init__(self, _("Convert Timestamp To Date"))

	def has_result(self):
		return True

	def activate(self, leaf):
		format_ = _FORMATS[__kupfer_settings__["date_format"]]
		tm = time.strftime(format_, time.localtime(int(leaf.object)))
		return TextLeaf(kupferstring.fromlocale(tm))

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		try:
			int(leaf.object)
		except ValueError:
			return False
		else:
			return True


class ConvertToTimestamp(Action):
	def __init__(self):
		Action.__init__(self, _("Convert Date To Timestamp"))

	def has_result(self):
		return True

	def activate(self, leaf):
		tm = _try_to_convert_text_to_date(leaf.object)
		return TextLeaf(str(int(time.mktime(tm))))

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		return _try_to_convert_text_to_date(leaf.object) is not None
