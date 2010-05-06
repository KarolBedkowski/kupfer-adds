# -*- coding: UTF-8 -*-
'''
Extented settings classes that depends on (c)json module.
'''

__version__ = "2010-05-06"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"


try:
	import cjson
	json_decoder = cjson.decode
	json_encoder = cjson.encode
except ImportError:
	import json
	json_decoder = json.loads
	json_encoder = json.dumps

from kupfer import pretty
from kupfer.core.settings import ExtendedSetting


class JsonExtendedSetting (ExtendedSetting):
	''' Base class for object that store and load settings in Json format '''

	_preserve_attr = []

	def load(self, plugin_id, key, config_value):
		''' load value for @plugin_id and @key, @config_value is value
		stored in regular Kupfer config for plugin/key'''
		if self._preserve_attr and config_value:
			try:
				values = dict(json_decoder(config_value))
			except Exception, err:
				pretty.print_error('Error decoding config value', plugin_id,
						key, config_value, err)
			else:
				for key in self._preserve_attr:
					setattr(self, key, values.get(key))

	def save(self, plugin_id, key):
		''' Save value for @plugin_id and @key.
		@Return value that should be stored in Kupfer config for
		plugin/key (string)'''
		if not self._preserve_attr:
			return None
		values = dict((key, getattr(self, key)) for key in self._preserve_attr)
		return json_encoder(values)
