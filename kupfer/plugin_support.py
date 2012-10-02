import sys

import gobject

keyring = None

from kupfer import pretty
from kupfer import config
from kupfer.core import settings
from kupfer.core import plugins
from kupfer import utils

__all__ = [
	"UserNamePassword",
	"PluginSettings",
	"check_dbus_connection",
	"check_keyring_support",
]

def _is_core_setting(key):
	return key.startswith("kupfer_")

class PluginSettings (gobject.GObject, pretty.OutputMixin):
	"""Allows plugins to have preferences by assigning an instance
	of this class to the plugin's __kupfer_settings__ attribute.

	Setting values are accessed by the getitem operator [] with
	the setting's 'key' attribute

	Signals:

		plugin-setting-changed: key, value

	"""
	__gtype_name__ = "PluginSettings"

	def __init__(self, *setdescs):
		"""Create a settings collection by passing in dictionaries
		as arguments, where each dictionary must have the following keys:
			key
			type
			value (default value)
			label (localized label)

		the @key may be any string except strings starting with
		'kupfer_', which are reserved
		"""
		gobject.GObject.__init__(self)
		self.setting_descriptions = {}
		self.setting_key_order = []
		self.signal_connection = -1
		req_keys = set(("key", "value", "type", "label"))
		for desc in setdescs:
			if not req_keys.issubset(desc.keys()):
				missing = req_keys.difference(desc.keys())
				raise KeyError("Plugin setting missing keys: %s" % missing)
			self.setting_descriptions[desc["key"]] = dict(desc)
			self.setting_key_order.append(desc["key"])

	def __iter__(self):
		return iter(self.setting_key_order)

	def initialize(self, plugin_name):
		"""Init by reading from global settings and setting up callbacks"""
		setctl = settings.GetSettingsController()
		for key in self:
			value_type = self.setting_descriptions[key]["type"]
			value = setctl.get_plugin_config(plugin_name, key, value_type)
			if value is not None:
				self[key] = value
			elif _is_core_setting(key):
				default = self.setting_descriptions[key]["value"]
				setctl.set_plugin_config(plugin_name, key, default, value_type)
		setctl.connect("value-changed", self._value_changed, plugin_name)
		# register for unload notification
		if not plugin_name.startswith("core."):
			plugins.register_plugin_unimport_hook(plugin_name,
					self._disconnect_all, plugin_name)

	def __getitem__(self, key):
		return self.setting_descriptions[key]["value"]
	def __setitem__(self, key, value):
		value_type = self.setting_descriptions[key]["type"]
		self.setting_descriptions[key]["value"] = value_type(value)
		if not _is_core_setting(key):
			self.emit("plugin-setting-changed::"+str(key), key, value)

	def _value_changed(self, setctl, section, key, value, plugin_name):
		"""Preferences changed, update object"""
		if key in self and plugin_name in section:
			self[key] = value

	def get_value_type(self, key):
		"""Return type of setting @key"""
		return self.setting_descriptions[key]["type"]
	def get_label(self, key):
		"""Return label for setting @key"""
		return self.setting_descriptions[key]["label"]
	def get_alternatives(self, key):
		"""Return alternatives for setting @key (if any)"""
		return self.setting_descriptions[key].get("alternatives")
	def get_tooltip(self, key):
		"""Return tooltip string for setting @key (if any)"""
		return self.setting_descriptions[key].get("tooltip")

	def connect_settings_changed_cb(self, callback, *args):
		self.signal_connection = \
				self.connect("plugin-setting-changed", callback, *args)

	def _disconnect_all(self, plugin_name):
		if self.signal_connection != -1:
			self.disconnect(self.signal_connection)


# Arguments: Key, Value
# Detailed by the key
gobject.signal_new("plugin-setting-changed", PluginSettings,
		gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_DETAILED,
		gobject.TYPE_BOOLEAN,
		(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT))

# Plugin convenience functions for dependencies

_has_dbus_connection = None

def check_dbus_connection():
	"""
	Check if a connection to the D-Bus daemon is available,
	else raise ImportError with an explanatory error message.

	For plugins that can not be used without contact with D-Bus;
	if this check is used, the plugin may use D-Bus and assume it
	is available in the Plugin's code.
	"""
	global _has_dbus_connection
	if _has_dbus_connection is None:
		import dbus
		try:
			dbus.Bus()
			_has_dbus_connection = True
		except dbus.DBusException:
			_has_dbus_connection = False
	if not _has_dbus_connection:
		raise ImportError(_("No D-Bus connection to desktop session"))

class UserNamePassword (settings.ExtendedSetting):
	''' Configuration type for storing username/password values.
	Username is stored in Kupfer config, password in keyring '''
	def __init__(self, obj=None):
		settings.ExtendedSetting.__init__(self)
		self.username = None
		self.password = None
		if obj:
			self.username = obj.username
			self.password = obj.password

	def __repr__(self):
		return '<UserNamePassword "%s", %s>' % (self.username,
		                                        bool(self.password))

	@classmethod
	def is_backend_encrypted(cls):
		import keyring.core
		return keyring.core.get_keyring().supported() == 1

	@classmethod
	def get_backend_name(cls):
		import keyring.core
		import keyring.backend
		keyring_map = {
				keyring.backend.GnomeKeyring : _("GNOME Keyring"),
				keyring.backend.KDEKWallet : _("KWallet"),
				keyring.backend.UncryptedFileKeyring: _("Unencrypted File"),
			}
		kr = keyring.get_keyring()
		keyring_name = keyring_map.get(type(kr), type(kr).__name__)
		return keyring_name

	def load(self, plugin_id, key, username):
		self.password = keyring.get_password(plugin_id, username)
		self.username = username

	def save(self, plugin_id, key):
		''' save @user_password - store password in keyring and return username
		to save in standard configuration file '''
		keyring.set_password(plugin_id, str(self.username), self.password)
		return self.username

def check_keyring_support():
	"""
	Check if the UserNamePassword class can be used,
	else raise ImportError with an explanatory error message.
	"""
	global keyring
	# if gnomekeyring exists, block kde libraries
	old_pykde4 = sys.modules.get('PyKDE4')
	try:
		import gnomekeyring
	except ImportError:
		pass
	else:
		sys.modules['PyKDE4'] = None
	try:
		import keyring
	except ImportError:
		global UserNamePassword
		class UserNamePassword (object):
			pass
		raise
	else:
		# Configure the fallback keyring's configuration file if used
		import keyring.backend
		kr = keyring.get_keyring()
		if hasattr(kr, "crypted_password"):
			keyring.set_keyring(keyring.backend.UncryptedFileKeyring())
			kr = keyring.get_keyring()
		if hasattr(kr, "file_path"):
			kr.file_path = config.save_config_file("keyring.cfg")
	finally:
		# now unblock kde libraries again
		if old_pykde4:
			sys.modules['PyKDE4'] = old_pykde4


def _plugin_configuration_error(plugin, err):
	pretty.print_error(__name__, err)


def _is_valid_terminal(term_dict):
	if len(term_dict["argv"]) < 1:
		return False
	exe = term_dict["argv"][0]
	return bool(utils.lookup_exec_path(exe))


_available_alternatives = {
	"terminal": {
		"filter": _is_valid_terminal,
		"required_keys": {
			'name': unicode,
			'argv': list,
			'exearg': str,
			'desktopid': str,
			'startup_notify': bool,
		},
	},
	"icon_renderer": {
		"filter": None,
		"required_keys": {
			'name': unicode,
			'renderer': object,
		},
	},
}

_alternatives = {
	"terminal": {},
	"icon_renderer": {},
}


def register_alternative(caller, category_key, id_, **kwargs):
	"""
	Register a new alternative for the category @category_key

	@caller: Must be the caller's plugin id (Plugin __name__ variable)

	@id_ is a string identifier for the object to register
	@kwargs are the keyed arguments for the alternative constructor

	Returns True with success
	"""
	caller = str(caller)
	category_key = str(category_key)
	id_ = str(id_)

	if category_key not in _available_alternatives:
		_plugin_configuration_error(caller,
				"Category '%s' does not exist" % category_key)
		return
	alt = _available_alternatives[category_key]
	id_ = caller + "." + id_
	kw_set = set(kwargs)
	req_set = set(alt["required_keys"])
	if not req_set.issubset(kw_set):
		_plugin_configuration_error(caller,
			"Configuration error for alternative '%s':" % category_key)
		_plugin_configuration_error(caller, "Missing keys: %s" %
				(req_set - kw_set))
		return
	_alternatives[category_key][id_] = kwargs
	pretty.print_debug(__name__,
		"Registered alternative %s: %s" % (category_key, id_))
	setctl = settings.GetSettingsController()
	setctl._update_alternatives(category_key, _alternatives[category_key],
	                            alt["filter"])

	# register the alternative to be unloaded
	plugin_id = ".".join(caller.split(".")[2:])
	if plugin_id and not plugin_id.startswith("core."):
		plugins.register_plugin_unimport_hook(plugin_id,
				_unregister_alternative, caller, category_key, id_)
	return True

def _unregister_alternative(caller, category_key, full_id_):
	"""
	Remove the alternative for category @category_key
	(this is done automatically at plugin unload)
	"""
	if category_key not in _available_alternatives:
		_plugin_configuration_error(caller,
				"Category '%s' does not exist" % category_key)
		return
	alt = _available_alternatives[category_key]
	id_ = full_id_
	try:
		del _alternatives[category_key][id_]
	except KeyError:
		_plugin_configuration_error(caller,
				"Alternative '%s' does not exist" % (id_, ))
		return
	pretty.print_debug(__name__,
		"Unregistered alternative %s: %s" % (category_key, id_))
	setctl = settings.GetSettingsController()
	setctl._update_alternatives(category_key, _alternatives[category_key],
	                            alt["filter"])
	return True


