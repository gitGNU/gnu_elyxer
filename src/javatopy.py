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
# Alex 20091226
# Port a Java program to a Python equivalent. Used to port MathToWeb.

import sys
import os.path
from io.fileline import *
from parse.position import *
from util.trace import Trace


def readargs(args):
  "Read arguments from the command line"
  del args[0]
  if len(args) == 0:
    usage()
    return
  inputfile = args[0]
  del args[0]
  outputfile = os.path.splitext(inputfile)[0] + '.py'
  if len(args) > 0:
    outputfile = args[0]
    del args[0]
  if len(args) > 0:
    usage()
    return
  return inputfile, outputfile

def usage():
  Trace.error('Usage: javatopy.py filein.java [fileout.py]')
  return

class JavaPorter(object):
  "Ports a Java file."

  javatokens = [
      'if', 'do', 'while', '&&', '||', '=', '==', '!=', 'import', 'public',
      'class', 'private', 'protected', 'else', 'try', 'return'
      ]

  def __init__(self):
    self.depth = 0
    self.inclass = None
    self.inmethod = None

  def topy(self, inputfile, outputfile):
    "Port the Java input file to Python."
    pos = FilePosition(inputfile)
    tok = Tokenizer(pos)
    writer = LineWriter(outputfile)
    while not tok.pos.finished():
      line = self.processstatement(tok)
      if len(line.strip()) > 0:
        writer.writeline(line)
    writer.close()

  def processstatement(self, tok):
    "Process a single statement and return the result."
    statement = self.parsestatement(tok)
    Trace.debug('Statement: ' + statement)
    tok.pos.skipspace()
    while tok.pos.finished():
      Trace.debug('Closing bracket }, endings: ' + unicode(tok.pos.endinglist))
      self.closebracket(tok)
      tok.pos.skipspace()
    return statement

  def parsestatement(self, tok):
    "Parse a single statement."
    indent = self.depth * '  '
    token = tok.next()
    Trace.debug('Token: ' + token)
    if token in self.javatokens:
      return indent + self.translatetoken(tok)
    statement = indent + self.processtoken(tok)
    statement += ' ' + self.parseupto(';', tok)
    return statement

  def processpart(self, tok):
    "Process a part of a statement."
    tok.next()
    return ' ' + self.processtoken(tok)

  def processtoken(self, tok):
    "Process a single token."
    if tok.current() in tok.javasymbols:
      return self.translatesymbol(tok)
    return tok.current()

  def translatetoken(self, tok):
    "Translate a java token."
    token = tok.current()
    if token == 'import':
      return self.translateimport(tok)
    if token in ['public', 'private', 'protected']:
      if self.inclass:
        return self.translateinternal(tok)
      else:
        return self.translateclass(tok)
    if token == 'if':
      result = self.parseifparens(tok)
      self.openbracket(tok)
      return result
    if token in ['else', 'try']:
      self.openbracket(tok)
      return token + ':'
    if token == 'return':
      result = self.parseupto(';', tok)
      Trace.debug('Return found: ' + result)
      return token + ' ' + result
    Trace.error('Untranslated token ' + token)
    return token

  def translateimport(self, tok):
    "Translate an import statement."
    tok.pos.globincluding(';')
    return ''

  def translateclass(self, tok):
    "Translate a class definition."
    token = tok.next()
    if token != 'class':
      Trace.error('Unrecognized token: ' + token)
      return ''
    name = tok.next()
    self.inclass = name
    self.openbracket(tok)
    # pos.pushending('}')
    return 'class ' + name + ':'

  def translateinternal(self, tok):
    "Translate an internal element (attribute or method)."
    token = tok.next()
    if token == self.inclass:
      # constructor
      if tok.next() != '(':
        Trace.error('Constructor missing (, found ' + tok.current())
      return self.translatemethod(token, tok)
    name = tok.next()
    if tok.pos.current() == ';':
      return self.translateemptyattribute(name)
    if tok.next() != '(':
      return self.translateattribute(name)
    return self.translatemethod(name, tok)

  def translatemethod(self, name, tok):
    "Translate a class method."
    self.inmethod = name
    pars = self.parseparameters(tok)
    self.openbracket(tok)
    # pos.pushending('}')
    result = 'def ' + name + '(self' + '):'
    return result

  def translateemptyattribute(self, name):
    "Translate an empty attribute definition."
    return name + ' = None'

  def translateattribute(self, name, tok):
    "Translate a class attribute."
    tok.pos.pushending(';')
    result = name
    while not tok.pos.finished():
      result += ' ' + tok.next()
    tok.pos.popending()
    return result

  def parseparameters(self, tok):
    "Parse the parameters of a method definition."
    pars = []
    tok.pos.pushending(')')
    while not tok.pos.finished():
      type = tok.next()
      name = tok.next()
      pars.append(name)
      if not tok.pos.finished() and tok.next() != ',':
        Trace.error('Missing comma, found ' + tok.current())
    tok.pos.popending()
    return pars
  
  def translatesymbol(self, tok):
    "Translate a java symbol."
    if tok.current() == '"':
      result = tok.current() + tok.pos.globincluding('"')
      while result.endswith('\\"') and not result.endswith('\\\\"'):
        result += tok.pos.globincluding('"')
      Trace.debug('quoted sequence: ' + result)
      return result
    if tok.current() == '\'':
      result = tok.current()
      while not tok.pos.checkskip('\''):
        result += tok.pos.currentskip()
      return result + '\''
    if tok.current() == '}':
      Trace.error('Erroneously closing }')
      self.closebracket(tok)
      return ''
    if tok.current() == '(':
      result = self.parseparens(tok)
      return result
    if tok.current() == ')':
      Trace.error('Erroneously closing )')
      return ')'
    if tok.current() in tok.modified:
      return tok.modified[tok.current()]
    return tok.current()

  def parseifparens(self, tok):
    "Parse a () from an if clause."
    if tok.next() != '(':
      Trace.error('No opening ( for an if clause.')
      return
    return 'if ' + self.parseparens(tok) + ':'

  def parseparens(self, tok):
    "Parse the contents inside ()."
    result = self.parseupto(')', tok)
    return '(' + result + ')'

  def parseupto(self, ending, tok):
    "Parse the tokenizer up to the supplied ending."
    tok.pos.pushending(ending)
    result = ''
    while not tok.pos.finished():
      result += self.processpart(tok)
      tok.pos.skipspace()
    tok.pos.popending(ending)
    if len(result) > 0:
      result = result[1:]
    return result

  def openbracket(self, tok):
    "Open a {."
    while tok.next() != '{':
      Trace.error('Ignored token before {: ' + tok.current())
      if tok.pos.finished():
        Trace.error('Finished while waiting for {')
        return
    self.depth += 1
    tok.pos.pushending('}')

  def closebracket(self, tok):
    "Close a }."
    self.depth -= 1
    if tok.pos.popending('}') != '}':
      exit()

class Tokenizer(object):
  "Tokenizes a parse position."

  unmodified = [
      '&', '|', '=', '!', '(', ')', '{', '}', '.', '+', '-', '"', ',', '/',
      '*', '<', '>', '\'', '[', ']', '%',
      '!=','++','--','<=','>=', '=='
      ]
  modified = {
      '&&':'and', '||':'or'
      }
  javasymbols = unmodified + modified.keys()

  def __init__(self, pos):
    self.pos = pos
    self.currenttoken = None

  def next(self):
    "Get the next single token."
    while not self.pos.finished():
      token = self.extracttoken()
      if token:
        self.currenttoken = token
        return token
    return ''

  def current(self):
    "Get the current token."
    return self.currenttoken

  def extracttoken(self):
    "Extract a single token."
    self.pos.skipspace()
    if self.pos.finished():
      return None
    if self.pos.checkskip('//'):
      comment = self.pos.globexcluding('\n')
      return None
    if self.pos.checkskip('/*'):
      while not self.pos.checkskip('/'):
        comment = self.pos.globincluding('*')
      return None
    if self.isalphanumeric(self.pos.current()):
      return self.pos.glob(self.isalphanumeric)
    if self.pos.current() in self.javasymbols:
      result = self.pos.currentskip()
      while result + self.pos.current() in self.javasymbols:
        result += self.pos.currentskip()
      return result
    current = self.pos.currentskip()
    Trace.error('Unrecognized character: ' + current)
    return current

  def isalphanumeric(self, char):
    "Detect if a character is alphanumeric or underscore."
    if char.isalpha():
      return True
    if char.isdigit():
      return True
    if char == '_':
      return True
    return False

  def finished(self):
    "Find out if the parse position has finished."
    return self.pos.finished()

inputfile, outputfile = readargs(sys.argv)
Trace.debugmode = True
if inputfile:
  JavaPorter().topy(inputfile, outputfile)
  Trace.message('Conversion done, running ' + outputfile)
  os.system('python ' + outputfile)

