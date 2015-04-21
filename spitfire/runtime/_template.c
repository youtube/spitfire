#include <Python.h>

// Constant used when checking for the presence of the skip_filter attribute.
static PyObject *Skip_Filter_PyString = NULL;
static PyObject *filter_function_name = NULL;
static struct _typeobject *baked_SanitizedPlaceholder = NULL;


/* The original Python function:
# wrap the underlying filter call so that items don't get filtered multiple
# times (avoids double escaping)
# fixme: this could be a hotspot, having to call getattr all the time seems
# like it might be a bit pokey
def py_filter_function(self, value, placeholder_function):
  if type(value) == baked.SanitizedPlaceholder:
    return value
  elif (placeholder_function is not None and
      getattr(placeholder_function, 'skip_filter', False)):
    return value
  else:
    return self._filter_function(value)
*/
// filter_function checks if the value should be filtered. If it is a
// SanitizedPlaceholder or the placeholder_function has a skip_filter
// annotation, there is no need to filter. Otherwise, call
// self._filter_function.
static PyObject *
filter_function(PyObject *self, PyObject *args)
{
  PyObject *obj;
  PyObject *value;
  PyObject *fn;
  if (!PyArg_UnpackTuple(args, "filter_function", 3, 3, &obj, &value, &fn)) {
    return NULL;
  }
  if (Py_TYPE(value) == baked_SanitizedPlaceholder) {
    Py_INCREF(value);
    return value;
  }
  if (fn != Py_None) {
    PyObject *is_skip_filter = PyObject_GetAttr(fn, Skip_Filter_PyString);
    if (is_skip_filter == NULL) {
      PyErr_Clear();
    } else if (PyObject_IsTrue(is_skip_filter)) {
      Py_DECREF(is_skip_filter);
      Py_INCREF(value);
      return value;
    } else {
      Py_DECREF(is_skip_filter);
    }
  }
  // TODO: Manually get the function and call it to avoid tuple
  // creation in PyObject_CallMethodObjArgs.
  return PyObject_CallMethodObjArgs(obj, filter_function_name, value, NULL);
}


// Function registration table: name-string -> function-pointer
static struct PyMethodDef template_functions[] = {
  {"filter_function", (PyCFunction)filter_function, METH_VARARGS},
  {NULL, NULL}
};


PyMODINIT_FUNC
init_template(void)
{
  PyObject *m, *baked_module;
  m = Py_InitModule3("_template", template_functions, "Template Module");
  if (m == NULL)
    return;

  Skip_Filter_PyString = PyString_InternFromString("skip_filter");
  filter_function_name = PyString_InternFromString("_filter_function");

  baked_module = PyImport_ImportModule("spitfire.runtime.baked");
  if (baked_module == NULL)
    return;

  baked_SanitizedPlaceholder = (struct _typeobject *)
      PyObject_GetAttrString(baked_module, "SanitizedPlaceholder");
  Py_DECREF(baked_module);
  if (baked_SanitizedPlaceholder == NULL)
    return;
}
