// Copyright 2015 The Spitfire Authors. All Rights Reserved.
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

#include <Python.h>

// Constant used when checking for the presence of the skip_filter attribute.
static PyObject *Skip_Filter_PyString = NULL;
static PyObject *filter_function_name = NULL;
static struct _typeobject *baked_SanitizedPlaceholder = NULL;


// Base Template with filter_function method.
typedef struct {
  PyObject_HEAD
} BaseSpitfireTemplateObject;


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
  PyObject *value;
  PyObject *fn = Py_None;
  if (!PyArg_UnpackTuple(args, "filter_function", 1, 2, &value, &fn)) {
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
  return PyObject_CallMethodObjArgs(self, filter_function_name, value, NULL);
}


// Function registration table: name-string -> function-pointer
static struct PyMethodDef template_methods[] = {
  {"filter_function", (PyCFunction)filter_function, METH_VARARGS},
  {NULL, NULL}
};


// BaseSpitfireTemplate Type.
static PyTypeObject BaseSpitfireTemplateType = {
  PyObject_HEAD_INIT(NULL)
  0,                                        /* ob_size */
  "template.BaseSpitfireTemplate",          /* tp_name */
  sizeof(BaseSpitfireTemplateObject),       /* tp_basicsize */
  0,                                        /* tp_itemsize */
  0,                                        /* tp_dealloc */
  0,                                        /* tp_print */
  0,                                        /* tp_getattr */
  0,                                        /* tp_setattr */
  0,                                        /* tp_compare */
  0,                                        /* tp_repr */
  0,                                        /* tp_as_number */
  0,                                        /* tp_as_sequence */
  0,                                        /* tp_as_mapping */
  0,                                        /* tp_hash */
  0,                                        /* tp_call */
  0,                                        /* tp_str */
  0,                                        /* tp_getattro */
  0,                                        /* tp_setattro */
  0,                                        /* tp_as_buffer */
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */
  0,                                        /* tp_doc */
  0,                                        /* tp_traverse */
  0,                                        /* tp_clear */
  0,                                        /* tp_richcompare */
  0,                                        /* tp_weaklistoffset */
  0,                                        /* tp_iter */
  0,                                        /* tp_iternext */
  template_methods,                         /* tp_methods */
  0,                                        /* tp_members */
  0,                                        /* tp_getset */
  0,                                        /* tp_base */
  0,                                        /* tp_dict */
  0,                                        /* tp_descr_get */
  0,                                        /* tp_descr_set */
  0,                                        /* tp_dictoffset */
  0,                                        /* tp_init */
  0,                                        /* tp_alloc */
  0,                                        /* tp_new */
};


// Function registration table: name-string -> function-pointer
static struct PyMethodDef module_methods[] = {
  {NULL} // Sentinel
};


PyMODINIT_FUNC
init_template(void)
{
  // Set interned strings.
  Skip_Filter_PyString = PyString_InternFromString("skip_filter");
  filter_function_name = PyString_InternFromString("_filter_function");

  // Get SanitizedPlaceholder from the baked module.
  PyObject *baked_module = PyImport_ImportModule("spitfire.runtime.baked");
  if (baked_module == NULL)
    return;
  baked_SanitizedPlaceholder = (struct _typeobject *)
      PyObject_GetAttrString(baked_module, "SanitizedPlaceholder");
  Py_DECREF(baked_module);
  if (baked_SanitizedPlaceholder == NULL)
    return;


  // Setup module and class.
  PyObject *m;
  BaseSpitfireTemplateType.tp_new = PyType_GenericNew;
  if (PyType_Ready(&BaseSpitfireTemplateType) < 0)
    return;

  m = Py_InitModule3("_template", module_methods, "Template Module");
  if (m == NULL)
    return;

  Py_INCREF(&BaseSpitfireTemplateType);
  PyModule_AddObject(m, "BaseSpitfireTemplate",
                     (PyObject *)&BaseSpitfireTemplateType);
}
