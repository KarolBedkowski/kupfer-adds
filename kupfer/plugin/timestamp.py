__kupfer_name__ = _("Timestamp")
__kupfer_actions__ = ("Convert", "ConvertToTimestamp")
__description__ = _("Convert timestamp to the human readable format")
__version__ = ""
__author__ = "Jan Krajdl <spm@spamik.cz>"

from kupfer import plugin_support

__kupfer_settings__ = plugin_support.PluginSettings(
    {
        "key": "date_format",
        "label": _("Output format"),
        "type": str,
        "value": "dd.MM.yyyy hh:mm:ss",
        "alternatives": (
            "MM/dd/yyyy hh:mm:ss",
            "yyyy/MM/dd hh:mm:ss",
            )
        },
)

import time
from kupfer.objects import Action, TextLeaf

_FORMATS = {
    "dd.MM.yyyy hh:mm:ss": "%d.%m.%Y %H:%M:%S",
    "MM/dd/yyyy hh:mm:ss": "%m/%d/%Y %H:%M:%S",
    "yyyy/MM/dd hh:mm:ss": "%Y/%m/%d %H:%M:%S"
}

class Convert(Action):
    rank_adjust = 2

    def __init__(self):
        Action.__init__(self, _("Convert from timestamp"))
        
    def has_result(self):
        return True
    
    def activate(self, leaf):
        format = _FORMATS[__kupfer_settings__["date_format"]]
        tm = time.strftime(format, time.localtime(int(leaf.object)))
        return TextLeaf(tm)

    def item_types(self):
        yield TextLeaf

    def valid_for_item(self, leaf):
        try:
            int(leaf.object)
            return True
        except:
            return False

class ConvertToTimestamp(Action):
    rank_adjust = 10

    def __init__(self):
        Action.__init__(self, _("Convert from date"))

    def has_result(self):
        return True

    def activate(self, leaf):
        format = _FORMATS[__kupfer_settings__["date_format"]]
        tm = time.strptime(leaf.object, format)
        return TextLeaf(str(int(time.mktime(tm))))

    def item_types(self):
        yield TextLeaf

    def valid_for_item(self, leaf):
        format = _FORMATS[__kupfer_settings__["date_format"]]
        try:
            time.strptime(leaf.object, format)
            return True
        except:
            return False
