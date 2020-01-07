# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

#from builtins import zip
import re
import string
import unicodedata
import sys
if sys.version_info[0] < 3:
    ascii_lowercase = string.lowercase
    ascii_uppercase = string.uppercase
else:
    ascii_lowercase = string.ascii_lowercase
    ascii_uppercase = string.ascii_uppercase


normal_characters = ascii_lowercase + ascii_uppercase
mangled_character_names = [
    'LATIN SMALL LETTER A WITH RING ABOVE',
    'LATIN SMALL LETTER THORN',
    'LATIN SMALL LETTER C WITH CIRCUMFLEX',
    'LATIN SMALL LETTER D WITH CARON',
    'LATIN SMALL LETTER E WITH GRAVE',
    'LATIN SMALL LETTER F WITH HOOK',
    'LATIN SMALL LETTER G WITH CIRCUMFLEX',
    'LATIN SMALL LETTER H WITH STROKE',
    'LATIN SMALL LETTER I WITH TILDE',
    'LATIN SMALL LETTER J WITH CIRCUMFLEX',
    'LATIN SMALL LETTER K WITH CEDILLA',
    'LATIN SMALL LETTER L WITH ACUTE',
    'SCRIPT CAPITAL M',
    'LATIN SMALL LETTER N WITH ACUTE',
    'LATIN SMALL LETTER ETH',
    'GREEK SMALL LETTER RHO',
    'LATIN SMALL LETTER O WITH OGONEK',
    'LATIN SMALL LETTER R WITH CARON',
    'LATIN SMALL LETTER S WITH ACUTE',
    'LATIN SMALL LETTER T WITH STROKE',
    'LATIN SMALL LETTER U WITH DOUBLE GRAVE',
    'LATIN SMALL LETTER V WITH TILDE',
    'LATIN SMALL LETTER W WITH DOT BELOW',
    'LATIN SMALL LETTER X WITH DOT ABOVE',
    'GREEK SMALL LETTER GAMMA',
    'LATIN SMALL LETTER Z WITH HOOK',
    'LATIN CAPITAL LETTER A WITH CIRCUMFLEX',
    'LATIN SMALL LETTER SHARP S',
    'LATIN CAPITAL LETTER C WITH ACUTE',
    'LATIN CAPITAL LETTER D WITH STROKE',
    'LATIN CAPITAL LETTER E WITH MACRON',
    'LATIN CAPITAL LETTER F WITH DOT ABOVE',
    'LATIN CAPITAL LETTER G WITH CIRCUMFLEX',
    'LATIN CAPITAL LETTER H WITH CIRCUMFLEX',
    'LATIN CAPITAL LETTER I WITH MACRON',
    'LATIN CAPITAL LETTER J WITH CIRCUMFLEX',
    'LATIN CAPITAL LETTER K WITH CEDILLA',
    'LATIN CAPITAL LETTER L WITH ACUTE',
    'LATIN CAPITAL LETTER M WITH DOT ABOVE',
    'LATIN CAPITAL LETTER N WITH ACUTE',
    'LATIN CAPITAL LETTER O WITH BREVE',
    'LATIN CAPITAL LETTER P WITH DOT ABOVE',
    'LATIN CAPITAL LETTER O WITH OGONEK AND MACRON',
    'LATIN CAPITAL LETTER R WITH CARON',
    'LATIN CAPITAL LETTER S WITH ACUTE',
    'LATIN CAPITAL LETTER T WITH STROKE',
    'LATIN CAPITAL LETTER U WITH TILDE',
    'LATIN CAPITAL LETTER V WITH TILDE',
    'LATIN CAPITAL LETTER W WITH CIRCUMFLEX',
    'CYRILLIC CAPITAL LETTER ZHE',
    'LATIN CAPITAL LETTER Y WITH CIRCUMFLEX',
    'LATIN CAPITAL LETTER Z WITH ACUTE',
]

char_map = dict(list(zip(normal_characters, [unicodedata.lookup(name)
                                        for name in mangled_character_names])))


# return a string with interesting unicode characters to make sure
# an application is handling unicode correctly
def i18n_mangled_message(msg):
    return ''.join([char_map.get(c, c) for c in msg])


whitespace_regex = re.compile('\s+', re.UNICODE)


def normalize_whitespace(text):
    return whitespace_regex.sub(' ', text)
