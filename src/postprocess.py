#! /usr/bin/env python
# -*- coding: utf-8 -*-

#   eLyXer -- convert LyX source files to HTML output.
#
#   Copyright (C) 2009 Alex Fernández
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

# --end--
# Alex 20090324
# eLyXer postprocessor code

from container import *
from link import *
from trace import Trace
from structure import *
from layout import *


class Group(Container):
  "A silly group of containers"

  def __init__(self):
    self.output = ContentsOutput()

  def contents(self, contents):
    self.contents = contents
    return self

  def __str__(self):
    return 'Group: ' + str(self.contents)

class PostBiblio(object):
  "Insert a Bibliography legend before the first item"

  processedclass = Bibliography

  def postprocess(self, element, last):
    "If we have the first bibliography insert a tag"
    if isinstance(last, Bibliography):
      return element
    tag = TaggedText().constant('Bibliography', 'h1 class="biblio"')
    return Group().contents([tag, element])

class PostLayout(object):
  "Numerate an indexed layout"

  processedclass = Layout

  ordered = ['Chapter', 'Section', 'Subsection', 'Subsubsection', 'Paragraph']
  unique = ['Part', 'Book']

  def __init__(self):
    self.startinglevel = 0
    self.number = []
    self.uniques = dict()

  def postprocess(self, element, last):
    "Generate a number and place it before the text"
    if element.type in PostLayout.unique:
      level = PostLayout.unique.index(element.type)
      number = self.generateunique(element.type)
    elif element.type in PostLayout.ordered:
      level = PostLayout.ordered.index(element.type)
      number = self.generate(level)
    else:
      return element
    element.contents.insert(0, Constant(number + u' '))
    return element

  def generateunique(self, type):
    "Generate a number to place in the title but not to append to others"
    if not type in PostLayout.unique:
      self.uniques[type] = 0
    self.uniques[type] += 1
    return type + ' ' + self.uniques[type] + '.'

  def generate(self, level):
    "Generate a number in the given level"
    if self.number == [] and level == 1:
      # starting at level 1
      self.startinglevel = 1
    level -= self.startinglevel
    if len(self.number) > level:
      self.number = self.number[:level + 1]
    else:
      while len(self.number) <= level:
        self.number.append(0)
    self.number[level] += 1
    return self.dotseparated()

  def dotseparated(self):
    "Get the number separated by dots: 1.1.3"
    dotsep = ''
    if len(self.number) == 0:
      Trace.error('Empty number')
      return '.'
    for number in self.number:
      dotsep += '.' + str(number)
    return dotsep[1:]

class PostNestedList(object):
  "Postprocess a nested list"

  processedclass = DeeperList

  def postprocess(self, deeper, last):
    "Run the postprocessor on the nested list"
    postproc = Postprocessor()
    i = 0
    while i < len(deeper.contents):
      part = deeper.contents[i]
      result = postproc.postprocess(part)
      deeper.contents[i] = result
      i += 1
    # one additional item to flush the list
    deeper.contents.append(postproc.postprocess(BlackBox()))
    return deeper

class PendingList(object):
  "A pending list"

  def __init__(self):
    self.contents = []
    self.type = None

  def additem(self, item):
    "Add a list item"
    Trace.debug('Pending ' + str(len(self.contents)) + ': ' + str(item))
    self.contents += item.contents
    self.type = item.type
    Trace.debug('Added ' + str(item.contents))

  def addnested(self, nested):
    "Add a nested list item"
    if self.empty():
      Trace.error('No items in list to insert ' + str(nested))
      return
    item = self.contents[-1]
    Trace.debug('Adding ' + str(nested) + ' to end of ' + str(item))
    self.contents[-1].contents.append(nested)

  def generatelist(self):
    "Get the resulting list"
    if not self.type:
      return Group().contents(self.contents)
    tag = ListItem.typetags[self.type]
    Trace.debug('List from ' + str(self))
    return TaggedText().complete(self.contents, tag, True)

  def empty(self):
    return len(self.contents) == 0

  def __str__(self):
    result = 'pending ' + str(self.type) + ': ['
    for element in self.contents:
      result += str(element) + ', '
    if len(self.contents) > 0:
      result = result[:-2]
    return result + ']'

class PostListPending(object):
  "Check if there is a pending list"

  def __init__(self):
    self.pending = PendingList()

  def postprocess(self, element, last):
    "If a list element do not return anything;"
    "otherwise return the whole pending list"
    original = element
    if isinstance(element, ListItem):
      element = self.processitem(element)
    elif isinstance(element, DeeperList):
      element = self.processnested(element)
    if not self.generatepending(original):
      return element
    Trace.debug('Generating ' + str(self.pending))
    list = self.pending.generatelist()
    self.pending.__init__()
    return Group().contents([list, element])

  def processitem(self, item):
    "Process a list item"
    self.pending.additem(item)
    return BlackBox()

  def processnested(self, nested):
    "Process a nested list"
    self.pending.addnested(nested)
    return BlackBox()

  def generatepending(self, element):
    "Decide whether to generate the pending list"
    if self.pending.empty():
      return False
    if isinstance(element, ListItem):
      if not self.pending.type:
        return False
      if self.pending.type != element.type:
        return True
      return False
    if isinstance(element, DeeperList):
      return False
    return True

class Postprocessor(object):
  "Postprocess an element keeping some context"

  def __init__(self):
    self.stages = [PostBiblio(), PostLayout(), PostNestedList()]
    self.unconditional = [PostListPending()]
    self.stagedict = dict([(x.processedclass, x) for x in self.stages])
    self.last = None

  def postprocess(self, original):
    "Postprocess an element taking into account the last one"
    element = original
    if element.__class__ in self.stagedict:
      stage = self.stagedict[element.__class__]
      element = stage.postprocess(element, self.last)
    for stage in self.unconditional:
      element = stage.postprocess(element, self.last)
    self.last = original
    return element

