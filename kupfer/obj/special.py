__version__ = '2010-01-21'


from kupfer.obj.objects import RunnableLeaf
from kupfer import kupferui
from kupfer import uiutils


class PleaseConfigureLeaf(RunnableLeaf):
	""" Show information and allow to open preferences for given plugin """
	message = _("Please Configure Plugin")
	description = _("Plugin %s is not configured")

	def __init__(self, plugin_id, plugin_name):
		plugin_id = plugin_id.split('.')[-1]
		RunnableLeaf.__init__(self, plugin_id, self.message)
		self.plugin_name = plugin_name

	def wants_context(self):
		return True

	def run(self, ctx):
		kupferui.show_plugin_info(self.object, ctx.environment)

	def get_icon_name(self):
		return "preferences-desktop"

	def get_description(self):
		return self.description % self.plugin_name


class InvalidCredentialsLeaf(PleaseConfigureLeaf):
	description = _("Invalid user credentials for %s")


class ErrorLeaf(RunnableLeaf):
	def __init__(self, message, description=''):
		RunnableLeaf.__init__(self, message, message)
		self._description = description

	def run(self):
		uiutils.show_text_result(self.object + "\n" +  self.message,
				title=_("Error"))

	def get_icon_name(self):
		return 'gtk-dialog-error'

	def get_description(self):
		return self._description


