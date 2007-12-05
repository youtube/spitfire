import StringIO

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
    module_code.append_line('import spitfire.runtime.udn')
    module_code.append_line('from spitfire.runtime.udn import resolve_udn')
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
    if not node.extends_nodes and not node.library:
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
    import_clause = self.generate_python(
      self.build_code(node.identifier)[0])
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
    if node.else_:
      else_code_node = CodeNode('else:')
      for n in node.else_:
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

  def codegenASTListLiteralNode(self, node):
    return [CodeNode('[%s]' % ', '.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.child_nodes]))]

  def codegenASTTupleLiteralNode(self, node):
    return [CodeNode('(%s)' % ', '.join([
      self.generate_python(self.build_code(n)[0])
      for n in node.child_nodes]))]

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

    code_node = CodeNode(ASTFunctionNode_tmpl[0] % vars())
    for n in node.child_nodes:
      code_child_nodes = self.build_code(n)
      code_node.extend(code_child_nodes)
    return [code_node]
  
  # fixme: don't know if i still need this - a 'template function'
  # has an implicit return of the buffer built in - might be simpler
  # to code that rather than adding a return node during the analyze
  #def codegenASTReturnNode(self, node):
  #  code_node = self.codegenDefault(node)

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


#ASTTextNode_tmpl = ['buffer.write(u"""%(value)s""")']

# ASTOptionalWhitespaceNode_tmpl = ASTTextNode_tmpl

# ASTWhitespaceNode_tmpl = ASTTextNode_tmpl

# ASTNewlineNode_tmpl = ASTTextNode_tmpl

ASTFunctionNode_tmpl = ['def %(name)s(%(parameter_list)s):']

# ASTFunctionInitNode_tmpl = ['buffer = self.new_buffer()']

#ASTReturnNode_tmpl = ['return %(expression)s']

ASTCallFunctionNode_tmpl = ['%(expression)s(%(arg_list)s)']

ASTForNode_tmpl = ['for %(target_list)s in %(expression_list)s:']

# ASTPlaceholderNode_tmpl = [
# 'self.resolve_placeholder("%(name)s", local_vars=locals())']

#ASTPlaceholderSubstitutionNode_tmpl = [
#  'buffer.write("%%s" %% %(placeholder)s)']

ASTTargetNode_tmpl = ['%(name)s']

ASTIdentifierNode_tmpl = ['%(name)s']
ASTAssignIdentifierNode_tmpl = ASTIdentifierNode_tmpl

ASTLiteralNode_tmpl = ['%(value)r']

ASTBreakNode_tmpl = ['break']

ASTContinueNode_tmpl = ['continue']

