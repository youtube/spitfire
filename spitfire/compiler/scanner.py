import yappsrt

import spitfire.compiler.parser

# SpitfireScanner uses the order of the match, not the length of the match to
# determine what token to return. I'm not sure how fragille this is long-term,
# but it seems to have been the right solution for a number of small problems
# allong the way.

class SpitfireScanner(spitfire.compiler.parser._SpitfireParserScanner):
  def __init__(self, *args):
    super(SpitfireScanner, self).__init__(*args)
    self._restrict_cache = {}

  def token(self, i, restrict=0):
    """Get the i'th token, and if i is one past the end, then scan
    for another token; restrict is a list of tokens that
    are allowed, or 0 for any token."""
    if i == len(self.tokens):
      self.scan(restrict)
    if i < len(self.tokens):
      # Make sure the restriction is more restricted
      if restrict and self.restrictions[i]:
        if not self.restrictions[i].issuperset(restrict):
          raise NotImplementedError(
            "Unimplemented: restriction set changed", restrict, self.restrictions[i])
        return self.tokens[i]
      elif not restrict and not self.restrictions[i]:
        return self.tokens[i]
    raise yappsrt.NoMoreTokens(i, len(self.tokens), self.tokens[i], restrict, self.restrictions[i], self.tokens)
  
  def scan(self, restrict):
    """Should scan another token and add it to the list, self.tokens,
    and add the restriction to self.restrictions"""
    # Keep looking for a token, ignoring any in self.ignore
    while True:
      # Search the patterns for the longest match, with earlier
      # tokens in the list having preference
      best_match = -1
      best_pat = '(error)'

      # Cache the list of patterns we check to avoid unnecessary iteration
      restrict = frozenset(restrict)
      patterns = self._restrict_cache.get(restrict, None)
      if patterns is None:
        patterns = [pair for pair in self.patterns if not restrict or pair[0] in restrict]
        self._restrict_cache[restrict] = patterns

      for p, regexp in patterns:
        m = regexp.match(self.input, self.pos)
        if m and len(m.group(0)) > best_match:
          # We got a match that's better than the previous one
          best_pat = p
          best_match = len(m.group(0))
          # msolo: use the first match, not the 'best'
          break
      # If we didn't find anything, raise an error
      if best_pat == '(error)' and best_match < 0:
        msg = "Bad Token"
        if restrict:
          msg = "Trying to find one of " + ', '.join(restrict)
        raise yappsrt.SyntaxError(self.pos, msg)

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
