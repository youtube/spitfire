# Yapps 2.0 Runtime
#
# This module is needed to run generated parsers.
from __future__ import division, print_function

import logging
import re
import sys
if sys.version_info[0] < 3:
    import StringIO
else:
    import io as StringIO

class SyntaxError(Exception):
  """When we run into an unexpected token, this is the exception to use"""
  def __init__(self, pos=-1, msg="Bad Token"):
    Exception.__init__(self)
    self.pos = pos
    self.msg = msg
  def __repr__(self):
    if self.pos < 0:
      return "#<syntax-error>"
    else:
      return "SyntaxError[@ char %s: %s]" % (repr(self.pos), self.msg)


class NoMoreTokens(Exception):
  """Another exception object, for when we run out of tokens"""
  pass

class FatalParseError(Exception):
  """We have to fail-stop for one reason or another."""

class Scanner(object):
  def __init__(self, patterns, ignore, input):
    """Patterns is [(terminal,regex)...]
    Ignore is [terminal,...];
    Input is a string"""
    self.tokens = []
    self.restrictions = []
    self.input = input
    self.pos = 0
    self.ignore = ignore
    # The stored patterns are a pair (compiled regex,source
    # regex).  If the patterns variable passed in to the
    # constructor is None, we assume that the class already has a
    # proper .patterns list constructed
    if patterns is not None:
      self.patterns = []
      for k, r in patterns:
        self.patterns.append( (k, re.compile(r)) )

  def file_position(self, token_index):
    """Returns the in-file start position of the token at the given index.

    The token must be one of the already read tokens,
    or the next one we are about to read.  Otherwise,
    this raises IndexError."""
    if token_index < len(self.tokens):
      return self.tokens[token_index][0]
    elif token_index == len(self.tokens):
      return self.pos
    else:
      raise IndexError(
          "Can't determine file position of future token %d." % token_index)

  def token(self, i, restrict=0):
    """Get the i'th token, and if i is one past the end, then scan
    for another token; restrict is a list of tokens that
    are allowed, or 0 for any token."""
    if i == len(self.tokens):
      self.scan(restrict)
    if i < len(self.tokens):
      # Make sure the restriction is more restricted
      if restrict and self.restrictions[i]:
        for r in restrict:
          if r not in self.restrictions[i]:
            raise NotImplementedError(
              "Unimplemented: restriction set changed", r, self.restrictions[i])
        return self.tokens[i]
      elif not restrict and not self.restrictions[i]:
        return self.tokens[i]
    raise NoMoreTokens(i, len(self.tokens), self.tokens[i], restrict, self.restrictions[i], self.tokens)

  def __repr__(self):
    """Print the last 10 tokens that have been scanned in"""
    output = ''
    for t in self.tokens[-10:]:
      output = '%s\n  (@%s)  %s  =  %s' % (output,t[0],t[2],repr(t[3]))
    return output

  def scan(self, restrict):
    """Should scan another token and add it to the list, self.tokens,
    and add the restriction to self.restrictions"""
    # Keep looking for a token, ignoring any in self.ignore
    while 1:
      # Search the patterns for the longest match, with earlier
      # tokens in the list having preference
      best_match = -1
      best_pat = '(error)'
      for p, regexp in self.patterns:
        # First check to see if we're ignoring this token
        if restrict and p not in restrict and p not in self.ignore:
          continue
        m = regexp.match(self.input, self.pos)
        if m and len(m.group(0)) > best_match:
          # We got a match that's better than the previous one
          best_pat = p
          best_match = len(m.group(0))

      # If we didn't find anything, raise an error
      if best_pat == '(error)' and best_match < 0:
        msg = "Bad Token"
        if restrict:
          msg = "Trying to find one of "+ ', '.join(restrict)
        raise SyntaxError(self.pos, msg)

      # If we found something that isn't to be ignored, return it
      if best_pat not in self.ignore:
        # Create a token with this data
        token = (self.pos, self.pos+best_match, best_pat,
                 self.input[self.pos:self.pos+best_match])
        self.pos = self.pos + best_match
        # Only add this token if it's not in the list
        # (to prevent looping)
        if not self.tokens or token != self.tokens[-1]:
          self.tokens.append(token)
          self.restrictions.append(restrict)
          return
      else:
        # This token should be ignored ..
        self.pos = self.pos + best_match


class Parser(object):
  def __init__(self, scanner):
    self._scanner = scanner
    self._pos = 0

  def _peek(self, *types):
    """Returns the token type for lookahead; if there are any args
    then the list of args is the set of token types to allow"""
    tok = self._scanner.token(self._pos, types)
    return tok[2]

  def _scan(self, type):
    """Returns the matched text, and moves to the next token"""
    tok = self._scanner.token(self._pos, [type])
    if tok[2] != type:
      raise SyntaxError(tok[0], 'Trying to find %s (%s)' % (type, tok[0]))
    self._pos = 1+self._pos
    return tok[3]

  @property
  def file_position(self):
    return self._scanner.file_position(self._pos)


def format_error(input, err, scanner):
  """This is a really dumb long function to print error messages nicely."""
  error_message = StringIO.StringIO()
  p = err.pos
  print("error position", p, file=error_message)
  # Figure out the line number
  line = input[:p].count('\n')
  print(err.msg, "on line", repr(line+1) + ":", file=error_message)
  # Now try printing part of the line
  text = input[max(p-80, 0):p+80]
  p = p - max(p-80, 0)

  # Strip to the left
  i = text[:p].rfind('\n')
  j = text[:p].rfind('\r')
  if i < 0 or (0 <= j < i): i = j
  if 0 <= i < p:
    p = p - i - 1
  text = text[i+1:]

  # Strip to the right
  i = text.find('\n', p)
  j = text.find('\r', p)
  if i < 0 or (0 <= j < i):
    i = j
  if i >= 0:
    text = text[:i]

  # Now shorten the text
  while len(text) > 70 and p > 60:
    # Cut off 10 chars
    text = "..." + text[10:]
    p = p - 7

  # Now print the string, along with an indicator
  print('> ', text.replace('\t', ' ').encode(sys.getdefaultencoding()), file=error_message)
  print('> ', ' '*p + '^', file=error_message)
  print('List of nearby tokens:', scanner, file=error_message)
  return error_message.getvalue()


def wrap_error_reporter(parser, rule):
  try:
    return getattr(parser, rule)()
  except SyntaxError as e:
    logging.exception('syntax error')
    input = parser._scanner.input
    try:
      error_msg = format_error(input, e, parser._scanner)
    except ImportError:
      error_msg = 'Syntax Error %s on line\n' % (e.msg, 1 + input[:e.pos].count())
  except NoMoreTokens as e:
    error_msg = 'Could not complete parsing; stopped around here:\n%s\n%s' % (parser._scanner, e)
  raise FatalParseError(error_msg)
