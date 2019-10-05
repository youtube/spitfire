# Copyright 2016 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

from builtins import object
import sys


class RecordedExcInfo(object):
    """Container for exception info recorded by the RecordedFunction class."""

    def __init__(self, exc_info):
        """Initializer.

        Args:
        exc_info: Tuple returned by sys.exc_info()
        """
        self._exc_info = exc_info

    def GetExcInfo(self):
        """Returns the tuple returned by sys.exc_info() stored in this
        object."""
        return self._exc_info

    def GetException(self):
        """Returns the exception object thrown by a wrapped function."""
        exc_type, exc_obj, unused_traceback = self._exc_info

        # Correctly handles exceptions that are not Exception sub-classes.
        if exc_obj is not None:
            return exc_obj
        return exc_type


class RecordedFunction(object):
    """Records the parameters and results of every call to a function.

    Use it like this:

      def power(num, exp=2):
        return num ** exp

      recorded_power = RecordedFunction(power)
      self.assertEqual(recorded_power(2), 4)
      self.assertEqual(recorded_power(2, 3), 8)
      self.assertEqual(recorded_power(5, exp=1), 5)

      # Look at how it was called and how it responded.
      expected_calls = [
        ((2,), {}), # first call
        ((2, 3), {}), # second call
        ((5,), {"exp": 1}) # third call
      ]
      self.assertListEqual(recorded_power.GetCalls(), expected_calls)

      expected_results = [
        4,
        8,
        5
      ]
      self.assertListEqual(recorded_power.GetResults(), expected_results)

    If at any time an exception is thrown by the wrapped function, an instance
    of the RecordedExcInfo class that contains the exception will be placed in
    the results list. This ensures that the indexes of GetCalls() and
    GetResults() match up regardless of what happens.

    Example:

      def thrower(e):
        raise e

      recorded_thrower = RecordedFunction(thrower)

      class MyError(Exception): pass

      expected_exception = MyError()

      try:
        recorded_thrower(expected_exception)
      except MyError as e:
        self.assertIs(e, expected_exception)

      # Look at how it was called and how it responded.
      expected_calls = [
        ((expected_exception,), {})
      ]
      self.assertListEqual(recorded_thrower.GetCalls(), expected_calls)

      results = recorded_thrower.GetResults()

      self.assertEqual(len(results), 1)
      self.assertIsInstance(results[0], RecordedExcInfo)
      self.assertIs(results[0].GetException(), expected_exception)
    """

    def __init__(self, func):
        """Initializer.

        Args:
          func: Callable function to wrap with the recorder.
        """
        self._calls = []
        self._results = []
        self._func = func

    def __call__(self, *args, **kwargs):
        """Call the function with the supplied parameter, recording results.

        Args:
          *args: Positional arguments.
          **kwargs: Keyword arguments.

        Returns:
          Result of calling the wrapped function with the supplied parameters.
        """
        self._calls.append((args, kwargs))

        try:
            result = self._func(*args, **kwargs)
            self._results.append(result)
            return result
        except:
            self._results.append(RecordedExcInfo(sys.exc_info()))
            raise

    def GetCalls(self):
        """Get the list of calls made so far.

        Returns:
          Each entry in the list will be a tuple (args, kwargs) where:
            args: Tuple of positional arguments.
            kwargs: Dictionary of keyword arguments.
        """
        # Use a copy so callers can't modify the original.
        return self._calls[:]

    def GetResults(self):
        """Collect the list of results returned by the wrapped function.

        When the wrapped function raises an exception, an instance of the
        RecordedExcInfo class containing the exception will be placed in the
        results list since no actual value is available.

        Returns:
          The list of results returned by the wrapped function.
        """
        # Use a copy so callers can't modify the original.
        return self._results[:]
