// Copyright 2015 The Spitfire Authors. All Rights Reserved.
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

#include <Python.h>

// Constant used when checking for the presence of the skip_filter attribute.
static PyObject *Skip_Filter_PyString = NULL;

// SanitizedPlaceholder Object
typedef struct {
#if PY_MAJOR_VERSION >= 3

  PyUnicodeObject str;
#else
  PyStringObject str;
#endif
} SanitizedPlaceholderObject;

// Forward declare the type object.
static PyTypeObject SanitizedPlaceholderType;

// Python function that returns a SanitizedPlaceholder when value is a string,
// otherwise it just returns value. This function tries to follow the code in
// str_subtype_new.
static PyObject *
mark_as_sanitized(PyObject *self, PyObject *value)
{
#if PY_MAJOR_VERSION >= 3
  // If the value is not unicode, return it immediately.
  if (!PyUnicode_CheckExact(value)) {
    Py_INCREF(value);
    return value;
  }
  PyObject *args = Py_BuildValue("(N)", value);
  PyObject *obj = PyObject_CallObject((PyObject *) &SanitizedPlaceholderType, args);
  Py_DECREF(args);
  return obj;
#else
  // If the value is not a string, return it immediately.
  if (!PyString_CheckExact(value)) {
    Py_INCREF(value);
    return value;
  }
  // We know that value is a PyString at this point.
  Py_ssize_t size = PyString_GET_SIZE(value);
  // Allocate space for the SP object.
  PyObject *obj = PyType_GenericAlloc(&SanitizedPlaceholderType, size);
  if (obj == NULL) {
    return NULL;
  }
  SanitizedPlaceholderObject *sp_ptr = (SanitizedPlaceholderObject *)obj;
  // Set the hash and state.
  sp_ptr->str.ob_shash = ((PyStringObject *)value)->ob_shash;
  sp_ptr->str.ob_sstate = SSTATE_NOT_INTERNED;
  // Copy over the string including \0 using memcpy. This is faster than
  // instantiating a new string object.
  memcpy(sp_ptr->str.ob_sval, PyString_AS_STRING(value), size+1);
  return obj;
#endif
}

// Python function that checks if skip_filter is present on the function passed
// in. If skip_filter is present, call mark_as_sanitzied, otherwise return the
// value.
static PyObject *
runtime_mark_as_sanitized(PyObject *self, PyObject *args)
{
  PyObject *value;
  PyObject *fn;
  if (!PyArg_UnpackTuple(args, "_runtime_mark_as_sanitized",
                         2, 2, &value, &fn)){
    return NULL;
  }
  // If skip filter is present and true, build the sanitized placeholder.
  // Otherwise, just return the value.
  PyObject *is_skip_filter = PyObject_GetAttr(fn, Skip_Filter_PyString);
  if (is_skip_filter && PyObject_IsTrue(is_skip_filter)) {
    Py_DECREF(is_skip_filter);
    return mark_as_sanitized(NULL, value);
  }
  PyErr_Clear();
  Py_INCREF(value);
  Py_XDECREF(is_skip_filter);
  return value;
}

// SanitizedPlaceholder method for concat (+). A SanitizedPlaceholder is
// returned when both sides are SanitizedPlaceholders.
static PyObject *
sp_concat(PyObject *self, PyObject *other)
{
  PyObject *tmpself;
#if PY_MAJOR_VERSION >= 3
  tmpself = PyUnicode_Concat(self, other);
#else
  // PyString_Concat requires an INCREF on self.
  Py_INCREF(self);
  PyString_Concat(&self, other);
  tmpself = self;
#endif
  if (Py_TYPE(other) != &SanitizedPlaceholderType) {
    return tmpself;
  }
  // PyString_Concat copies self turning it back into a string. Calling
  // mark_as_sanitized turns it back into a SanitizedPlaceholder.
  return mark_as_sanitized(tmpself, tmpself);
}

// SanitizedPlaceholder method for mod (%). A SanitizedPlaceholder is returned
// when both values are SanitizedPlaceholders.
static PyObject *
sp_mod(PyObject *self, PyObject *other)
{
#if PY_MAJOR_VERSION >= 3
  PyObject *val = PyUnicode_Format(self, other);
#else
  PyObject *val = PyString_Format(self, other);
#endif
  if (Py_TYPE(other) != &SanitizedPlaceholderType) {
    return val;
  }
  // If the other value was a SanitizedPlaceholder, we want to turn the string
  // result from Py*_Format into a SanitizedPlaceholder. This currently
  // copies over the string which is not the most efficient way to do this.
  return mark_as_sanitized(self, val);
}

static PySequenceMethods sp_as_sequence = {
  0,                     /* sq_length */
  (binaryfunc)sp_concat, /* sq_concat */
  0,                     /* sq_repeat */
  0,                     /* sq_item */
  0,                     /* sq_slice */
  0,                     /* sq_ass_item */
  0,                     /* sq_ass_slice */
  0,                     /* sq_contains */
};

static PyNumberMethods sp_as_number = {
  0,      /* nb_add */
  0,      /* nb_subtract */
  0,      /* nb_multiply */
#if PY_MAJOR_VERSION < 3
  0,      /* nb_divide */
#endif
  sp_mod, /* nb_remainder */
};

// SanitizedPlaceholder Type.
static PyTypeObject SanitizedPlaceholderType = {
  PyVarObject_HEAD_INIT(NULL,0 )
  "baked.SanitizedPlaceholder",             /* tp_name */
  sizeof(SanitizedPlaceholderObject),       /* tp_basicsize */
  0,                                        /* tp_itemsize */
  0,                                        /* tp_dealloc */
  0,                                        /* tp_print */
  0,                                        /* tp_getattr */
  0,                                        /* tp_setattr */
  0,                                        /* tp_compare */
  0,                                        /* tp_repr */
  &sp_as_number,                            /* tp_as_number */
  &sp_as_sequence,                          /* tp_as_sequence */
  0,                                        /* tp_as_mapping */
  0,                                        /* tp_hash */
  0,                                        /* tp_call */
  0,                                        /* tp_str */
  0,                                        /* tp_getattro */
  0,                                        /* tp_setattro */
  0,                                        /* tp_as_buffer */
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE |
#if PY_MAJOR_VERSION >= 3
    Py_TPFLAGS_UNICODE_SUBCLASS,            /* tp_flags */
#else
    Py_TPFLAGS_CHECKTYPES |
    Py_TPFLAGS_STRING_SUBCLASS,             /* tp_flags */
#endif
  0,                                        /* tp_doc */
  0,                                        /* tp_traverse */
  0,                                        /* tp_clear */
  0,                                        /* tp_richcompare */
  0,                                        /* tp_weaklistoffset */
  0,                                        /* tp_iter */
  0,                                        /* tp_iternext */
  0,                                        /* tp_methods */
  0,                                        /* tp_members */
  0,                                        /* tp_getset */
  &PyUnicode_Type,                          /* tp_base */
  0,                                        /* tp_dict */
  0,                                        /* tp_descr_get */
  0,                                        /* tp_descr_set */
  0,                                        /* tp_dictoffset */
  0,                                        /* tp_init */
  0,                                        /* tp_alloc */
  0,                                        /* tp_new */
};

// Function registration table: name-string -> function-pointer
static struct PyMethodDef baked_functions[] = {
  {"_mark_as_sanitized", (PyCFunction)mark_as_sanitized, METH_O},
  {"_runtime_mark_as_sanitized", (PyCFunction)runtime_mark_as_sanitized,
   METH_VARARGS},
  {NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_baked",          /* m_name */
    "Baked Module",    /* m_doc */
    -1,                /* m_size */
    baked_functions,   /* m_methods */
    NULL,              /* m_reload */
    NULL,              /* m_traverse */
    NULL,              /* m_clear */
    NULL,              /* m_free */
};
#endif

PyObject* moduleinit(void)
{
  PyObject *m;

#if PY_MAJOR_VERSION >= 3
  Skip_Filter_PyString = PyUnicode_InternFromString("skip_filter");
  // Set the base type and the constructor.
  SanitizedPlaceholderType.tp_base = &PyUnicode_Type;
  SanitizedPlaceholderType.tp_init = PyUnicode_Type.tp_init;
#else
  Skip_Filter_PyString = PyString_InternFromString("skip_filter");
  // Set the base type and the constructor.
  SanitizedPlaceholderType.tp_base = &PyString_Type;
  SanitizedPlaceholderType.tp_init = PyString_Type.tp_init;
#endif

  if (PyType_Ready(&SanitizedPlaceholderType) < 0) {
    return NULL;
  }

  // Add exported functions to the module.
#if PY_MAJOR_VERSION >= 3
  m = PyModule_Create(&moduledef);
#else
  m = Py_InitModule3("_baked", baked_functions, "Baked Module");
#endif
  if (m == NULL) {
    return NULL;
  }

  Py_INCREF(&SanitizedPlaceholderType);
  PyModule_AddObject(m, "_SanitizedPlaceholder",
                     (PyObject *) &SanitizedPlaceholderType);
  return m;
}

#if PY_MAJOR_VERSION < 3
PyMODINIT_FUNC init_baked(void) { (void)moduleinit(); }
#else
PyMODINIT_FUNC PyInit__baked(void) { return moduleinit(); }
#endif
