import yappsrt

import spitfire.compiler.parser

# SpitfireScanner uses the order of the match, not the length of the match to
# determine what token to return. I'm not sure how fragille this is long-term,
# but it seems to have been the right solution for a number of small problems
# allong the way.

class SpitfireScanner(spitfire.compiler.parser.SpitfireParserScanner):
  def scan(self, restrict):
    """Should scan another token and add it to the list, self.tokens,
    and add the restriction to self.restrictions"""
    # Keep looking for a token, ignoring any in self.ignore
    while True:
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
