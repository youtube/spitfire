import cStringIO as StringIO

# yes, i know this is evil
from spitfire.compiler.ast import *

class CodegenError(Exception):
  pass


class CodeNode(object):
  def __init__(self, src_line=None):
    self.src_line = src_line
    self.child_nodes = []
    
  def append_line(self, line):
    self.append(CodeNode(line))
    
  def append(self, code_node):
    self.child_nodes.append(code_node)
    
  def extend(self, code_nodes):
    try:
      self.child_nodes.extend(code_nodes)
    except TypeError:
      raise CodegenError("can't add %s" % code_nodes)

  def __repr__(self):
    return '%s:%s' % (self.__class__.__name__, self.src_line)

    
# perform an in-order traversal of the AST and call the generate methods
# in this case, we are generating python source code that should be somewhat
# human-readable
class CodeGenerator(object):
  indent_str = '  '
  indent_level = 0

  # options - an AnalyzerOptions object
  def __init__(self, ast_root, options=None):
    self.ast_root = ast_root
    self.options = options
    self.output = StringIO.StringIO()
    

  def get_code(self):
    code_root = self.build_code(self.ast_root)[0]
    self.write_python(code_root, indent_level=-1)
    return self.output.getvalue().encode(self.ast_root.encoding)

  def generate_python(self, code_node):
    try:
      return code_node.src_line
    except AttributeError, e:
      raise CodegenError(
        "can't write code_node: %s\n\t%s" % (code_node, e))
    
  def write_python(self, code_node, indent_level):
    try:
      if code_node.src_line is not None:
        self.output.write(self.indent_str * indent_level)
        self.output.write(code_node.src_line)
        self.output.write('\n')
    except AttributeError:
      raise CodegenError("can't write code_node: %s" % code_node)

    for cn in code_node.child_nodes:
      self.write_python(cn, indent_level + 1)

  def build_code(self, ast_node):
    method_name = 'codegenAST%s' % ast_node.__class__.__name__
    method = getattr(self, method_name, self.codegenDefault)
    return method(ast_node)

  def codegenASTTemplateNode(self, node):
    module_code = CodeNode()
    module_code.append_line('#!/usr/bin/env python')
    module_code.append_line('# -*- coding: %s -*-' % node.encoding)
    module_code.append_line('')
    if node.import_nodes:
      module_code.append_line('# template imports')
      for n in node.import_nodes:
        module_code.extend(self.build_code(n))
      module_code.append_line('')
    if node.from_nodes:
      module_code.append_line('# template from imports')
      for n in node.from_nodes:
        module_code.extend(self.build_code(n))
      module_code.append_line('')
    extends = []
    for n in node.extends_nodes:
      extends.append(self.generate_python(self.build_code(n)[0]))
    if not extends:
      extends = ['spitfire.runtime.template.SpitfireTemplate']

    extends_clause = ', '.join(extends)
    classname = node.classname
    
    module_code.append_line('import spitfire.runtime')
    module_code.append_line('import spitfire.runtime.template')

    if self.options and self.options.cheetah_cheats:
      module_code.append_line('from Cheetah.NameMapper import valueFromSearchList as resolve_placeholder')
      module_code.append_line('from Cheetah.NameMapper import valueForKey as resolve_udn')
    else:
      module_code.append_line('from spitfire.runtime.udn import resolve_placeholder')
      module_code.append_line('from spitfire.runtime.udn import resolve_udn')
    module_code.append_line('from spitfire.runtime.template import template_method')
    module_code.append_line('')
    if node.cached_identifiers:
      module_code.append_line('# cached identifiers')
      for cached_ph in node.cached_identifiers:
        module_code.append_line('%s = None' % cached_ph.name)
      module_code.append_line('')
    
    class_code = CodeNode(
      'class %(classname)s(%(extends_clause)s):' % vars())
    module_code.append(class_code)
    for n in node.attr_nodes:
      class_code.extend(self.build_code(n))
      class_code.append_line('')
    
    for n in node.child_nodes:
      class_code.extend(self.build_code(n))
      class_code.append_line('')

    # if we aren't extending a template, build out the main function
    if (not node.extends_nodes and not node.library) or node.implements:
      class_code.extend(self.build_code(node.main_function))


    if self.options and self.options.enable_psyco:
      module_code.append_line('spitfire.runtime.template.enable_psyco(%(classname)s)' % vars())

    module_code.append_line(run_tmpl % vars(node))

    return [module_code]

  def codegenASTExtendsNode(self, node):
    return [CodeNode('.'.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.module_name_list]))]

  def codegenASTImportNode(self, node):
    return [CodeNode(
      'import %s' % '.'.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.module_name_list]))]

  def codegenASTFromNode(self, node):
    from_clause = '.'.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.module_name_list])
    import_clause = self.generate_python(self.build_code(node.identifier)[0])

    if node.alias:
      alias_clause = self.generate_python(self.build_code(node.alias)[0])
      return [CodeNode(
        'from %(from_clause)s import %(import_clause)s as %(alias_clause)s'
        % vars())]
    else:
      return [CodeNode(
        'from %(from_clause)s import %(import_clause)s' % vars())]

  def codegenASTPlaceholderSubstitutionNode(self, node):
    placeholder = self.generate_python(
      self.build_code(node.expression)[0])
    return [CodeNode(ASTPlaceholderSubstitutionNode_tmpl[0] % vars())]

  def codegenASTCallFunctionNode(self, node):
    expression = self.generate_python(
      self.build_code(node.expression)[0])
    if node.arg_list:
      arg_list = self.generate_python(
        self.build_code(node.arg_list)[0])
    else:
      arg_list = ''
    return [CodeNode(ASTCallFunctionNode_tmpl[0] % vars())]

  def codegenASTForNode(self, node):
    target_list = self.generate_python(
      self.build_code(node.target_list)[0])
    expression_list = self.generate_python(
      self.build_code(node.expression_list)[0])
    code_node = CodeNode(ASTForNode_tmpl[0] % vars())
    for n in node.child_nodes:
      code_node.extend(self.build_code(n))
    return [code_node]

  def codegenASTIfNode(self, node):
    test_expression = self.generate_python(
      self.build_code(node.test_expression)[0])
    if_code_node = CodeNode("if %(test_expression)s:" % vars())
    for n in node.child_nodes:
      if_code_node.extend(self.build_code(n))
    code_nodes = [if_code_node]
    if node.else_.child_nodes:
      else_code_node = CodeNode('else:')
      for n in node.else_.child_nodes:
        else_code_node.extend(self.build_code(n))
      code_nodes.append(else_code_node)
    return code_nodes


  def codegenASTTargetListNode(self, node):
    if len(node.child_nodes) == 1:
      return self.build_code(node.child_nodes[0])
    else:
      return [CodeNode('(%s)' % ', '.join(
        [self.generate_python(self.build_code(n)[0])
         for n in node.child_nodes]))]
  codegenASTExpressionListNode = codegenASTTargetListNode

  def codegenASTLiteralNode(self, node):
    if (self.options and not self.options.generate_unicode and
        isinstance(node.value, basestring)):
      return [CodeNode(repr(node.value.encode(self.ast_root.encoding)))]
    else:
      # generate unicode by default
      return [CodeNode('%(value)r' % vars(node))]
      

  def codegenASTListLiteralNode(self, node):
    return [CodeNode('[%s]' % ', '.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.child_nodes]))]

  def codegenASTTupleLiteralNode(self, node):
    return [CodeNode('(%s)' % ', '.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.child_nodes]))]

  def codegenASTDictLiteralNode(self, node):
    return [
      CodeNode('{%s}' %
               ', '.join([
      '%s: %s' % (self.generate_python(self.build_code(kn)[0]),
                  self.generate_python(self.build_code(vn)[0]))
      for kn, vn in node.child_nodes]))]
  
  def codegenASTParameterNode(self, node):
    if node.default:
      return [CodeNode('%s=%s' % (node.name, self.generate_python(
        self.build_code(node.default)[0])))]
    else:
      return [CodeNode('%s' % node.name)]

  def codegenASTAttributeNode(self, node):
    return [CodeNode('%s = %s' % (node.name, self.generate_python(
      self.build_code(node.default)[0])))]
    
  def codegenASTParameterListNode(self, node):
    if len(node.child_nodes) == 1:
      return self.build_code(node.child_nodes[0])
    else:
      return [CodeNode('%s' % ', '.join(
        [self.generate_python(self.build_code(n)[0])
         for n in node.child_nodes]))]

  codegenASTArgListNode = codegenASTParameterListNode
    
  def codegenASTGetUDNNode(self, node):
    #print "codegenASTGetUDNNode", id(node), "name", node.name, "expr", node.expression
    expression = self.generate_python(self.build_code(node.expression)[0])
    name = node.name
    return [CodeNode("resolve_udn(%(expression)s, '%(name)s')" % vars())]

  def codegenASTPlaceholderNode(self, node):
    name = node.name
    if name in ('has_var', 'get_var'):
      return [CodeNode("self.%(name)s" % vars())]
    elif self.options and self.options.cheetah_cheats:
      return [CodeNode(
        "resolve_placeholder(_self_search_list, '%(name)s')"
        % vars())]
    elif self.options and self.options.omit_local_scope_search:
      return [CodeNode(
        "resolve_placeholder('%(name)s', template=self, global_vars=_globals)"
        % vars())]
    else:
      return [CodeNode(
        "resolve_placeholder('%(name)s', template=self, local_vars=locals(), global_vars=_globals)"
        % vars())]

  def codegenASTReturnNode(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    return [CodeNode("return %(expression)s" % vars())]

  def codegenASTOptionalWhitespaceNode(self, node):
    #if self.ignore_optional_whitespace:
    #  return []
    return [CodeNode(ASTOptionalWhitespaceNode_tmpl[0] % vars(node))]

  def codegenASTSliceNode(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    slice_expression = self.generate_python(
      self.build_code(node.slice_expression)[0])
    return [CodeNode("%(expression)s[%(slice_expression)s]" % vars())]

  def codegenASTBinOpExpressionNode(self, node):
    left = self.generate_python(self.build_code(node.left)[0])
    right = self.generate_python(self.build_code(node.right)[0])
    operator = node.operator
    return [CodeNode('(%(left)s %(operator)s %(right)s)' % vars())]

  def codegenASTBinOpNode(self, node):
    left = self.generate_python(self.build_code(node.left)[0])
    right = self.generate_python(self.build_code(node.right)[0])
    operator = node.operator
    return [CodeNode('%(left)s %(operator)s %(right)s' % vars())]

  codegenASTAssignNode = codegenASTBinOpNode

  def codegenASTUnaryOpNode(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    operator = node.operator
    return [CodeNode('(%(operator)s %(expression)s)' % vars())]

  def codegenASTGetAttrNode(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    name = node.name
    return [CodeNode("%(expression)s.%(name)s" % vars())]

  def codegenASTFunctionNode(self, node):
    name = node.name
    if node.parameter_list:
      parameter_list = self.generate_python(
        self.build_code(node.parameter_list)[0])
    else:
      parameter_list = ''

    decorator_node = CodeNode('@template_method')
    # NOTE: for Cheetah compatibility, we have to handle the case where Cheetah
    # tries to pass a 'transaction' object through. hopefully this doesn't have
    # some other baggage coming with it.
    if self.options and self.options.cheetah_compatibility:
      if parameter_list:
        code_node = CodeNode('def %(name)s(%(parameter_list)s, **kargs):' % vars())
      else:
        code_node = CodeNode('def %(name)s(**kargs):' % vars())
    else:
      code_node = CodeNode('def %(name)s(%(parameter_list)s):' % vars())

    if self.options and self.options.cheetah_compatibility:
      if_cheetah = CodeNode("if 'trans' in kargs:")
      code_node.append(if_cheetah)
      if_cheetah.append(CodeNode("_buffer = kargs['trans'].response()"))
      else_spitfire = CodeNode('else:')
      else_spitfire.append(CodeNode('_buffer = self.new_buffer()'))
      code_node.append(else_spitfire)
    else:
      code_node.append(CodeNode('_buffer = self.new_buffer()'))
    code_node.append(CodeNode('_buffer_write = _buffer.write'))
    code_node.append(CodeNode('_globals = globals()'))
    code_node.append(CodeNode('_self_filter_function = self.filter_function'))
    
    if self.options and self.options.cheetah_cheats:
      code_node.append(CodeNode('_self_search_list = self.search_list + [_globals]'))

    for n in node.child_nodes:
      code_child_nodes = self.build_code(n)
      code_node.extend(code_child_nodes)
    if self.options.cheetah_compatibility:
      if_cheetah = CodeNode("if 'trans' not in kargs:")
      if_cheetah.append(CodeNode('return _buffer.getvalue()'))
      code_node.append(if_cheetah)
    else:
      code_node.append(CodeNode('return _buffer.getvalue()'))
    return [decorator_node, code_node]
  
  # fixme: don't know if i still need this - a 'template function'
  # has an implicit return of the buffer built in - might be simpler
  # to code that rather than adding a return node during the analyze
  #def codegenASTReturnNode(self, node):
  #  code_node = self.codegenDefault(node)

  def codegenASTBufferWrite(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    code_node = CodeNode('_buffer_write(%(expression)s)' % vars())
    return [code_node]

  def codegenASTEchoNode(self, node):
    node_list = []
    
    true_expression = self.generate_python(
      self.build_code(node.true_expression)[0])
    true_code = CodeNode('_buffer_write(%(true_expression)s)' % vars())
    if node.test_expression:
      test_expression = self.generate_python(
        self.build_code(node.test_expression)[0])
      if_code = CodeNode('if %(test_expression)s:' % vars())
      if_code.append(true_code)
      node_list.append(if_code)
    else:
      node_list.append(true_code)

    if node.false_expression:
      false_expression = self.generate_python(
        self.build_code(node.false_expression)[0])
      else_code = CodeNode('else:' % vars())
      else_code.append(
        CodeNode('_buffer_write(%(false_expression)s)' % vars()))
      node_list.append(else_code)
    return node_list

  def codegenASTCacheNode(self, node):
    cached_name = node.name
    expression = self.generate_python(self.build_code(node.expression)[0])
    # use dictionary syntax to get around coalescing 'global' statements
    #globalize_var = CodeNode('global %(cached_name)s' % vars())
    if_code = CodeNode("if %(cached_name)s is None:" % vars())
    if_code.append(CodeNode("_globals['%(cached_name)s'] = %(expression)s" % vars()))
    return [if_code]

  def codegenASTFilterNode(self, node):
    expression = self.generate_python(self.build_code(node.expression)[0])
    
    if node.filter_function_node == DefaultFilterFunction:
      filter_expression = '_self_filter_function'
    elif node.filter_function_node:
      filter_expression = self.generate_python(
        self.build_code(node.filter_function_node)[0])
    else:
      filter_expression = None

    if isinstance(node.expression, CallFunctionNode):
      # need the placeholder function expression to make sure that we don't
      # double escape the output of template functions
      # fixme: this is suboptimal if this expression is expensive - should the
      # optimizer fix this, or should we generate speedy code?
      placeholder_function_expression = self.generate_python(
        self.build_code(node.expression.expression)[0])
      if node.filter_function_node == DefaultFilterFunction:
        code_node = CodeNode(
          '%(filter_expression)s(%(expression)s, %(placeholder_function_expression)s)'
          % vars())
      elif node.filter_function_node:
        code_node = CodeNode(
          '%(filter_expression)s(self, %(expression)s, %(placeholder_function_expression)s)'
          % vars())
      else:
        code_node = CodeNode('%(expression)s' % vars())
    else:
      if node.filter_function_node == DefaultFilterFunction:
        code_node = CodeNode(
          '%(filter_expression)s(%(expression)s)' % vars())
      elif node.filter_function_node:
        code_node = CodeNode(
          '%(filter_expression)s(self, %(expression)s)' % vars())
      else:
        code_node = CodeNode('%(expression)s' % vars())
    return [code_node]


  def codegenDefault(self, node):
    v = globals()
    try:
      return [CodeNode(line % vars(node))
              for line in v['AST%s_tmpl' % node.__class__.__name__]]
    except KeyError, e:
      raise CodegenError("no codegen for %s %s" % (type(node), vars(node)))
  def codegen(self, node):
    return self.codegenDefault(node)[0]



run_tmpl = """

if __name__ == '__main__':
  import spitfire.runtime.runner
  spitfire.runtime.runner.run_template(%(classname)s)
"""



ASTFunctionNode_tmpl = ['def %(name)s(%(parameter_list)s):']

ASTCallFunctionNode_tmpl = ['%(expression)s(%(arg_list)s)']

ASTForNode_tmpl = ['for %(target_list)s in %(expression_list)s:']

ASTTargetNode_tmpl = ['%(name)s']

ASTIdentifierNode_tmpl = ['%(name)s']
ASTTemplateMethodIdentifierNode_tmpl = ['self.%(name)s']

ASTLiteralNode_tmpl = ['%(value)r']

ASTBreakNode_tmpl = ['break']

ASTContinueNode_tmpl = ['continue']
