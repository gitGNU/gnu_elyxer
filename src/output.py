#! /usr/bin/env python
# -*- coding: utf-8 -*-

# eLyXer: LyX to HTML converter
# Copyright 2009 Alex Fernández
# Published under the GPLv3, see LICENSE for details

# Alex 20090203
# eLyXer html outputters

import codecs
import datetime
from trace import Trace
from options import *


class EmptyOutput(object):
  "The output for some container"

  def gethtml(self, container):
    "Return empty HTML code"
    return []

class FixedOutput(object):
  "Fixed output"

  def gethtml(self, container):
    "Return constant HTML code"
    return container.html

class ContentsOutput(object):
  "Outputs the contents converted to HTML"

  def gethtml(self, container):
    "Return the HTML code"
    html = []
    for element in container.contents:
      html += element.gethtml()
    return html

class TagOutput(ContentsOutput):
  "Outputs an HTML tag surrounding the contents"

  def gethtml(self, container):
    "Return the HTML code"
    html = [self.getopen(container)]
    html += ContentsOutput.gethtml(self, container)
    html.append(self.getclose(container))
    return html

  def getopen(self, container):
    "Get opening line"
    if container.tag == '':
      return ''
    open = '<' + container.tag + '>'
    if container.breaklines:
      return open + '\n'
    return open

  def getclose(self, container):
    "Get closing line"
    if container.tag == '':
      return ''
    close = '</' + container.tag.split()[0] + '>'
    if container.breaklines:
      return '\n' + close + '\n'
    return close

class MirrorOutput(object):
  "Returns as output whatever comes along"

  def gethtml(self, container):
    "Return what is put in"
    return container.contents

class HeaderOutput(object):
  "Returns the HTML headers"

  def gethtml(self, container):
    "Return a constant header"
    html = [u'<?xml version="1.0" encoding="UTF-8"?>\n']
    html.append(u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n')
    html.append(u'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">\n')
    html.append(u'<head>\n')
    html.append(u'<link rel="stylesheet" href="lyx.css" type="text/css" media="screen"/>\n')
    html.append(u'<title>Converted document</title>')
    html.append('</head>\n')
    html.append('<body>\n')
    html.append('<div id="globalWrapper">\n')
    return html

class FooterOutput(object):
  "Return the HTML code for the footer"

  author = None

  def gethtml(self, container):
    "Footer HTML"
    html = []
    if FooterOutput.author and not Options.nocopy:
      html.append('<hr/>\n')
      year = datetime.date.today().year
      html.append('<p>Copyright (C) ' + str(year) + ' ' + FooterOutput.author
          + '</p>\n')
    html.append('</div>\n')
    html.append('</body>\n')
    html.append('</html>\n')
    return html

