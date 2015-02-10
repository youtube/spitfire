#include <Python.h>

// Constant used when checking for the presence of the skip_filter attribute.
static PyObject *Skip_Filter_PyString = NULL;

// SanitizedPlaceholder Object
typedef struct {
  PyStringObject str;
} SanitizedPlaceholderObject;

// SanitizedPlaceholder Type.
static PyTypeObject SanitizedPlaceholderType = {
  PyObject_HEAD_INIT(NULL)
  0,                                        /* ob_size */
  "baked.SanitizedPlaceholder",             /* tp_name */
  sizeof(SanitizedPlaceholderObject),       /* tp_basicsize */
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
  0,                                        /* tp_methods */
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


// Python function that returns a SanitizedPlaceholder when value is a string,
// otherwise it just returns value. This function tries to follow the code in
// str_subtype_new.
static PyObject *
mark_as_sanitized(PyObject *self, PyObject *value)
{
  // If the value is not a string, return it immediately.
  if (!PyString_CheckExact(value)) {
    Py_INCREF(value);
    return value;
  }
  // We know that value is a PyString at this point.
  Py_ssize_t size = PyString_GET_SIZE(value);
  // Allocate space for the SP object.
  PyObject *obj = PyType_GenericAlloc(&SanitizedPlaceholderType, size);
  SanitizedPlaceholderObject *sp_ptr = (SanitizedPlaceholderObject *)obj;
  // Set the hash and state.
  sp_ptr->str.ob_shash = ((PyStringObject *)value)->ob_shash;
  sp_ptr->str.ob_sstate = SSTATE_NOT_INTERNED;
  // Copy over the string including \0 using memcpy. This is faster than
  // instantiating a new string object.
  memcpy(sp_ptr->str.ob_sval, PyString_AS_STRING(value), size+1);
  return obj;
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


// Function registration table: name-string -> function-pointer
static struct PyMethodDef baked_functions[] = {
  {"_mark_as_sanitized", (PyCFunction)mark_as_sanitized, METH_O},
  {"_runtime_mark_as_sanitized", (PyCFunction)runtime_mark_as_sanitized,
   METH_VARARGS},
  {NULL, NULL}
};


PyMODINIT_FUNC
init_baked(void)
{
  PyObject *m;

  Skip_Filter_PyString = PyString_InternFromString("skip_filter");

  // Set the base type and the constructor.
  SanitizedPlaceholderType.tp_base = &PyString_Type;
  SanitizedPlaceholderType.tp_init = PyString_Type.tp_init;
  if (PyType_Ready(&SanitizedPlaceholderType) < 0)
    return;

  // Add exported functions to the module.
  m = Py_InitModule3("_baked", baked_functions, "Baked Module");
  if (m == NULL)
    return;

  Py_INCREF(&SanitizedPlaceholderType);
  PyModule_AddObject(m, "_SanitizedPlaceholder",
                     (PyObject *) &SanitizedPlaceholderType);
}
