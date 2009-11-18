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
# Alex 20090330
# eLyXer commands in formula processing

import sys
from gen.container import *
from ref.label import *
from util.trace import Trace
from util.clone import *
from conf.config import *
from math.formula import *
from math.bits import *


class FormulaCommand(FormulaBit):
  "A LaTeX command inside a formula"

  commandbits = []

  def detect(self, pos):
    "Find the current command"
    return pos.checkfor(FormulaConfig.starts['command'])

  def parsebit(self, pos):
    "Parse the command"
    command = self.extractcommand(pos)
    for bit in FormulaCommand.commandbits:
      if bit.recognize(command):
        newbit = Cloner.clone(bit)
        newbit.factory = self.factory
        newbit.setcommand(command)
        newbit.parsebit(pos)
        self.add(newbit)
        return newbit
    Trace.error('Unknown command ' + command)
    self.output = TaggedOutput().settag('span class="unknown"')
    self.add(FormulaConstant(command))

  def extractcommand(self, pos):
    "Extract the command from the current position"
    start = FormulaConfig.starts['command']
    if not pos.checkfor(start):
      Trace.error('Missing command start ' + start)
      return
    pos.skip(start)
    if pos.current().isalpha():
      # alpha command
      return start + pos.globalpha()
    # symbol command
    command = start + pos.current()
    pos.skip(pos.current())
    return command

  def process(self):
    "Process the internals"
    for bit in self.contents:
      bit.process()

class CommandBit(FormulaCommand):
  "A formula bit that includes a command"

  def recognize(self, command):
    "Recognize the command as own"
    return command in self.commandmap

  def setcommand(self, command):
    "Set the command in the bit"
    self.command = command
    self.original += command
    self.translated = self.commandmap[self.command]
 
  def parseparameter(self, pos):
    "Parse a parameter at the current position"
    if not self.factory.detectbit(pos):
      Trace.error('No parameter found at: ' + pos.remaining())
      return
    parameter = self.factory.parsebit(pos)
    self.add(parameter)
    return parameter

  def parsesquare(self, pos):
    "Parse a square bracket"
    bracket = SquareBracket()
    if not bracket.detect(pos):
      return None
    bracket.parsebit(pos)
    self.add(bracket)
    return bracket

class EmptyCommand(CommandBit):
  "An empty command (without parameters)"

  commandmap = FormulaConfig.commands

  def parsebit(self, pos):
    "Parse a command without parameters"
    self.contents = [FormulaConstant(self.translated)]

class AlphaCommand(EmptyCommand):
  "A command without paramters whose result is alphabetical"

  commandmap = FormulaConfig.alphacommands

  def parsebit(self, pos):
    "Parse the command and set type to alpha"
    EmptyCommand.parsebit(self, pos)
    self.type = 'alpha'

class OneParamFunction(CommandBit):
  "A function of one parameter"

  commandmap = FormulaConfig.onefunctions

  def parsebit(self, pos):
    "Parse a function with one parameter"
    self.output = TaggedOutput().settag(self.translated)
    self.parseparameter(pos)

  def simplifyifpossible(self):
    "Try to simplify to a single character."
    if self.original in FormulaConfig.alphacommands:
      self.output = FixedOutput()
      self.html = [FormulaConfig.alphacommands[self.original]]

class SymbolFunction(CommandBit):
  "Find a function which is represented by a symbol (like _ or ^)"

  commandmap = FormulaConfig.symbolfunctions

  def detect(self, pos):
    "Find the symbol"
    return pos.current() in SymbolFunction.commandmap

  def parsebit(self, pos):
    "Parse the symbol"
    self.setcommand(pos.current())
    pos.skip(self.command)
    self.output = TaggedOutput().settag(self.translated)
    self.parseparameter(pos)

class TextFunction(CommandBit):
  "A function where parameters are read as text."

  commandmap = FormulaConfig.textfunctions

  def parsebit(self, pos):
    "Parse a text parameter"
    self.output = TaggedOutput().settag(self.translated)
    bracket = Bracket().parsetext(pos)
    self.add(bracket)

  def process(self):
    "Set the type to font"
    self.type = 'font'

class LabelFunction(CommandBit):
  "A function that acts as a label"

  commandmap = FormulaConfig.labelfunctions

  def parsebit(self, pos):
    "Parse a literal parameter"
    self.key = Bracket().parseliteral(pos).literal

  def process(self):
    "Add an anchor with the label contents."
    self.type = 'font'
    self.label = Label().create(' ', self.key, type = 'eqnumber')
    self.contents = [self.label]
    # store as a Label so we know it's been seen
    Label.names[self.key] = self.label

class FontFunction(OneParamFunction):
  "A function of one parameter that changes the font"

  commandmap = FormulaConfig.fontfunctions

  def process(self):
    "Simplify if possible using a single character."
    self.type = 'font'
    self.simplifyifpossible()

class DecoratingFunction(OneParamFunction):
  "A function that decorates some bit of text"

  commandmap = FormulaConfig.decoratingfunctions

  def parsebit(self, pos):
    "Parse a decorating function"
    self.output = TaggedOutput().settag('span class="withsymbol"')
    self.type = 'alpha'
    symbol = self.translated
    tagged = TaggedBit().constant(symbol, 'span class="symbolover"')
    self.contents.append(tagged)
    parameter = self.parseparameter(pos)
    parameter.output = TaggedOutput().settag('span class="undersymbol"')
    self.simplifyifpossible()

class HybridFunction(CommandBit):
  "Read a function with two parameters: [] and {}"
  "The [] parameter is optional"

  commandmap = FormulaConfig.hybridfunctions

  def parsebit(self, pos):
    "Parse a function with [] and {} parameters"
    square = self.parsesquare(pos)
    bracket = self.parseparameter(pos)
    bracket.output = TaggedOutput().settag(self.translated)
    if self.command == '\sqrt':
      self.sqrt(square, bracket)
    elif self.command == '\unit':
      self.unit(square, bracket)
    else:
      Trace.error('Unknown hybrid function ' + self.command)
      return

  def sqrt(self, root, radical):
    "A square root -- process the root"
    if root:
      root.output = TaggedOutput().settag('sup')
    radix = TaggedBit().constant(u'√', 'span class="radical"')
    underroot = TaggedBit().complete(radical.contents, 'span class="root"')
    radical.contents = [radix, underroot]

  def unit(self, value, units):
    "A unit -- mark the units as font"
    units.type = 'font'

class FractionFunction(CommandBit):
  "A fraction with two parameters"

  commandmap = FormulaConfig.fractionfunctions

  def parsebit(self, pos):
    "Parse a fraction function with two parameters (optional alignment)"
    self.output = TaggedOutput().settag(self.translated[0])
    align = self.parsesquare(pos)
    parameter1 = self.parseparameter(pos)
    if not parameter1:
      Trace.error('Invalid fraction function ' + self.translated[0] + 
          ': missing first {}')
      return
    numerator = self.translated[1]
    if align and self.command == '\\cfrac':
      self.contents.pop(0)
      numerator = numerator[:-1] + '-' + align.contents[0].original + '"'
    parameter1.output = TaggedOutput().settag(numerator)
    self.contents.append(FormulaConstant(self.translated[2]))
    parameter2 = self.parseparameter(pos)
    if not parameter2:
      Trace.error('Invalid fraction function ' + self.translated[0] + 
          ': missing second {}')
      return
    parameter2.output = TaggedOutput().settag(self.translated[3])
    if align and self.command == '\\unitfrac':
      parameter1.type = 'font'
      parameter2.type = 'font'

class SpacingFunction(CommandBit):
  "A spacing function with two parameters"

  commandmap = FormulaConfig.spacingfunctions

  def parsebit(self, pos):
    "Parse a spacing function with two parameters"
    numparams = int(self.translated[1])
    parameter1 = Bracket().parseliteral(pos)
    if not parameter1:
      Trace.error('Missing first {} in function ' + self.command)
    parameter2 = None
    if numparams == 2:
      parameter2 = self.parseparameter(pos)
      if not parameter2:
        Trace.error('Missing second {} in spacing function ' + self.command)
        return
    else:
      self.add(FormulaConstant(' '))
    tag = self.translated[0].replace('$param', parameter1.literal)
    self.output = TaggedOutput().settag(tag)

FormulaFactory.bits += [FormulaCommand(), SymbolFunction()]
FormulaCommand.commandbits = [
    EmptyCommand(), AlphaCommand(), OneParamFunction(), DecoratingFunction(),
    FractionFunction(), FontFunction(), LabelFunction(), TextFunction(),
    HybridFunction(), SpacingFunction(),
    ]

