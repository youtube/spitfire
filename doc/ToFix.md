# Usability #

  * Support line continuations - all function arguments shouldn't need to be on the same line.

  * Reassigning a name with `#set` should raise a compiler error if it will get ignored anyway.

  * Support `not in`.


# Internationalization #

  * Support placeholder evaluation in $i18n() macros.

  * Check in memtable (previously called xle).

  * Build two implementations of the i18n macros. One using memtable and one using gettext.

