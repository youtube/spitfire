// Copyright 2009 The Spitfire Authors. All Rights Reserved.
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

#include "Python.h"
#include <string.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif


static PyObject *UDNResolveError;
static PyObject *PlaceholderError;
static PyObject *UnresolvedPlaceholder;
static PyObject *UndefinedAttribute;

#define TRUE 1
#define FALSE 0


static void
set_udn_resolve_error(PyObject *name, PyObject *namespace)
{
  PyObject *exception_args = NULL;

  exception_args = PyTuple_Pack(1, name);
  /* exception_args = PyTuple_Pack(2, name, namespace); */
  PyErr_SetObject(UDNResolveError, exception_args);
  Py_DECREF(exception_args);
}


static PyObject *
_resolve_udn(PyObject *obj, PyObject *name)
{
  PyObject *return_value = NULL;

  return_value = PyObject_GetAttr(obj, name);
  if (return_value != NULL) {
    return return_value;
  }

  PyErr_Clear();
  if (PyMapping_Check(obj)) {
    return_value = PyObject_GetItem(obj, name);
    if (return_value != NULL) {
      return return_value;
    }
  }

  PyErr_Clear();

  return return_value;
}


/* Wrapper functions to export into the Python module */

static PyObject *
udn_resolve_udn(PyObject *self, PyObject *args, PyObject *kargs)
{
  PyObject *obj, *name, *return_value, *error_args;
  int raise_exception = 0;

  static char *karg_list[] = {"obj", "name", "raise_exception", NULL};

  if (!PyArg_ParseTupleAndKeywords(args, kargs, "OO|i", karg_list,
                                   &obj, &name, &raise_exception)) {
    return NULL;
  }

  if (!(PyUnicode_Check(name) || PyBytes_Check(name))) {
    PyErr_SetString(PyExc_ValueError, "name must be string");
    return NULL;
  }

  return_value =  _resolve_udn(obj, name);
  /* return_value is NULL if the lookup failed */
  if (return_value == NULL) {
    if (raise_exception) {
      set_udn_resolve_error(name, obj);
    } else {
      error_args = Py_BuildValue("ON", name, PyObject_Dir(obj));
      return_value = PyObject_CallObject(UndefinedAttribute, error_args);
      Py_XDECREF(error_args);
    }
  }
  return return_value;
}


static PyObject *
udn_resolve_from_search_list(PyObject *self, PyObject *args, PyObject *keywds)
{
  PyObject *name_space = NULL;
  PyObject *return_value = NULL;
  PyObject *iterator = NULL;

  PyObject *search_list = NULL;
  PyObject *name;
  PyObject *default_value = NULL;

  static char *kwlist[] = {"search_list", "name", "default", NULL};

  if (!PyArg_ParseTupleAndKeywords(args, keywds, "OO|O", kwlist,
                                   &search_list, &name, &default_value)) {
    return NULL;
  }

  if (!(PyUnicode_Check(name) || PyBytes_Check(name))) {
    PyErr_SetString(PyExc_ValueError, "name must be string");
    return NULL;
  }

  iterator = PyObject_GetIter(search_list);
  if (iterator == NULL) {
    return_value = NULL;
    /* PyErr_SetString(PyExc_TypeError, "search_list is not iterable"); */
    goto done;
  }

  while ((name_space = PyIter_Next(iterator))) {
    return_value = _resolve_udn(name_space, name);
    Py_DECREF(name_space);
    if (return_value != NULL) {
      goto done;
    }
  }
done:
  if (return_value == NULL) {
    if (default_value != NULL) {
      return_value = default_value;
      Py_INCREF(return_value);
    } else {
      return_value = UnresolvedPlaceholder;
      Py_INCREF(return_value);
    }
  }
  Py_XDECREF(iterator);
  /* change the return value to be a bit more compatible with the way things
     work in the python code.
   */
  return return_value;
}


/* Method registration table: name-string -> function-pointer */

static struct PyMethodDef udn_methods[] = {
  {"_resolve_udn", (PyCFunction)udn_resolve_udn, METH_VARARGS|METH_KEYWORDS},
  {"_resolve_from_search_list", (PyCFunction)udn_resolve_from_search_list, METH_VARARGS|METH_KEYWORDS},
  {NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_udn",           /* m_name */
    "_udn module",    /* m_doc */
    -1,               /* m_size */
    udn_methods,      /* m_methods */
    NULL,             /* m_reload */
    NULL,             /* m_traverse */
    NULL,             /* m_clear */
    NULL,             /* m_free */
};
#endif

/* Initialization function (import-time) */

static PyObject* moduleinit(void)
{
  PyObject *m, *runtime_module;

#if PY_MAJOR_VERSION >= 3
  m = PyModule_Create(&moduledef);
#else
  m = Py_InitModule3("_udn", udn_methods, "_udn module");
#endif

  runtime_module = PyImport_ImportModule("spitfire.runtime");
  PlaceholderError = PyObject_GetAttrString(
    runtime_module, "PlaceholderError");
  UDNResolveError = PyObject_GetAttrString(runtime_module, "UDNResolveError");
  UnresolvedPlaceholder = PyObject_GetAttrString(
    runtime_module, "UnresolvedPlaceholder");
  UndefinedAttribute = PyObject_GetAttrString(
    runtime_module, "UndefinedAttribute");
  Py_DECREF(runtime_module);

  if (PyErr_Occurred())
    Py_FatalError("Can't initialize module _udn");
  return m;
}

#if PY_MAJOR_VERSION < 3
PyMODINIT_FUNC init_udn(void) { (void)moduleinit(); }
#else
PyMODINIT_FUNC PyInit__udn(void) { return moduleinit(); }
#endif

#ifdef __cplusplus
}
#endif
