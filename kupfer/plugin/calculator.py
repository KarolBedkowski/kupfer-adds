from __future__ import division
__kupfer_name__ = _("Calculator")
__kupfer_actions__ = ("Calculate", "CalculateOtherExpressions")
__description__ = _("Calculate mathematical expressions")
__version__ = "2012-06-10"
__author__ = "Ulrik Sverdrup <ulrik.sverdrup@gmail.com>"

"""
Changes:
	2012-06-09:
		+ calculate action for expression w/o =
	2012-06-10:
		+ separate Calculate action
		+ change localized decimal point symbol to .
"""

import locale
import cmath
import math

from kupfer.objects import Action, TextLeaf
from kupfer import pretty


class IgnoreResultException (Exception):
	pass


class KupferSurprise (float):
	"""kupfer

	cleverness to the inf**inf
	"""
	def __call__(self, *args):
		from kupfer import utils, version
		utils.show_url(version.WEBSITE)
		raise IgnoreResultException


class DummyResult (object):
	def __unicode__(self):
		return u"<Result of last expression>"


class Help (object):
	"""help()

	Show help about the calculator
	"""
	def __call__(self):
		import textwrap

		from kupfer import uiutils

		environment = make_environment(last_result=DummyResult())
		docstrings = []
		for attr in sorted(environment):
			if attr != "_" and attr.startswith("_"):
				continue
			val = environment[attr]
			if not callable(val):
				docstrings.append(u"%s = %s" % (attr, val))
				continue
			try:
				docstrings.append(val.__doc__)
			except AttributeError:
				pass
		formatted = []
		maxlen = 72
		left_margin = 4
		for docstr in docstrings:
			# Wrap the description and align continued lines
			docsplit = docstr.split("\n", 1)
			if len(docsplit) < 2:
				formatted.append(docstr)
				continue
			wrapped_lines = textwrap.wrap(docsplit[1].strip(),
					maxlen - left_margin)
			wrapped = (u"\n" + u" " * left_margin).join(wrapped_lines)
			formatted.append("%s\n    %s" % (docsplit[0], wrapped))
		uiutils.show_text_result("\n\n".join(formatted), _("Calculator"))
		raise IgnoreResultException

	def __complex__(self):
		return self()


def make_environment(last_result=None):
	"Return a namespace for the calculator's expressions to be executed in."
	environment = dict(vars(math))
	environment.update(vars(cmath))
	# define some constants missing
	if last_result is not None:
		environment["_"] = last_result
	environment["help"] = Help()
	environment["kupfer"] = KupferSurprise("inf")
	# make the builtins inaccessible
	environment["__builtins__"] = {}
	return environment


def format_result(res):
	cres = complex(res)
	parts = []
	if cres.real:
		parts.append(u"%s" % cres.real)
	if cres.imag:
		parts.append(u"%s" % complex(0, cres.imag))
	return u"+".join(parts) or u"%s" % res


class Calculate (Action):
	# since it applies only to special queries, we can up the rank
	rank_adjust = 10
	# global last_result
	last_result = {'last': None}

	def __init__(self):
		Action.__init__(self, _("Calculate"))

	def has_result(self):
		return True

	def activate(self, leaf):
		expr = leaf.object.lstrip("= ")

		# try to add missing parantheses
		brackets_missing = expr.count("(") - expr.count(")")
		if brackets_missing > 0:
			expr += ")" * brackets_missing
		# hack: change all decimal points (according to current locale) to '.'
		expr = expr.replace(locale.localeconv()['decimal_point'], '.')
		environment = make_environment(self.last_result['last'])
		pretty.print_debug(__name__, "Evaluating", repr(expr))
		try:
			result = eval(expr, environment)
			resultstr = format_result(result)
			self.last_result['last'] = result
		except IgnoreResultException:
			return
		except Exception, exc:
			pretty.print_error(__name__, type(exc).__name__, exc)
			resultstr = unicode(exc)
		return TextLeaf(resultstr)

	def item_types(self):
		yield TextLeaf

	def valid_for_item(self, leaf):
		text = leaf.object
		return text and text.startswith("=")

	def get_description(self):
		return None


class CalculateOtherExpressions(Calculate):
	""" Calcualte expressions that not starts with "=" """
	rank_adjust = 0

	def valid_for_item(self, leaf):
		text = leaf.object
		return text and not text.startswith("=") and (
				"+" in text or
				"-" in text or
				"*" in text or
				"/" in text or
				"^" in text or
				"&" in text or
				"|" in text or
				"~" in text)
