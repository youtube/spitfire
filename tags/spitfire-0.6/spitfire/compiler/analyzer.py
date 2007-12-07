import copy
import os.path

from spitfire.compiler.ast import *

def tree_walker(node):
  yield node
  for n in node.child_nodes:
    for ng in tree_walker(n):
      yield ng
  
class SemanticAnalyzerError(Exception):
  pass

class AnalyzerOptions(object):

  def __init__(self, **kargs):
    self.debug = False
    
    self.strip_optional_whitespace = False

    # adjacent text nodes become one single node
    self.collapse_adjacent_text = False
    
    # expensive dotted notations are aliased to a local variable for faster
    # lookups: write = self.buffer.write
    self.alias_invariants = False

    # when a variable defined in a block later is accessed, just use the raw
    # identifier, don't incure the cost of a resolve_placeholder call since you
    # know that this local variable will always resolve first
    self.directly_access_defined_variables = False

    self.enable_psyco = False
    
    self.__dict__.update(kargs)
  def update(self, **kargs):
    self.__dict__.update(kargs)
  
default_options = AnalyzerOptions()
o1_options = copy.copy(default_options)
o1_options.collapse_adjacent_text = True
o2_options = copy.copy(o1_options)
o2_options.alias_invariants = True
o2_options.directly_access_defined_variables = True
o3_options = copy.copy(o2_options)
o3_options.enable_psyco = True

optimizer_map = {
  0: default_options,
  1: o1_options,
  2: o2_options,
  3: o3_options,
  }

# convert the parse tree into something a bit more 'fat' and useful
# is this an AST? i'm not sure. it will be a tree of some sort
# this should simplify the codegen stage into a naive traversal
# even though this uses memory, i'll make a copy instead of decorating the
# original tree so i can compare the differences
# the other idea is that i can treat certain nodes as 'macros' to generate a
# few nodes that are more python-like
# additionally, there are some optimizations that are really more oriented at
# the parse tree, so i do them inline here. it's a bit split-brain, but it's
# seems easier.
class SemanticAnalyzer(object):
  def __init__(self, classname, parse_root, options=default_options):
    self.classname = classname
    self.parse_root = parse_root
    self.options = options
    self.ast_root = None
    self.template = None
    
  def get_ast(self):
    ast_node_list = self.build_ast(self.parse_root)
    if len(ast_node_list) != 1:
      raise SemanticAnalyzerError('ast must have 1 root node')
    self.ast_root = ast_node_list[0]
    return self.ast_root

  # build an AST node list from a single parse node
  # need the parent in case we are going to delete a node
  def build_ast(self, node):
    method_name = 'analyze%s' % node.__class__.__name__
    method = getattr(self, method_name, self.default_analyze_node)
    ast_node_list = method(node)
    try:
      if len(ast_node_list) != 1:
        return ast_node_list
    except TypeError, e:
      raise SemanticAnalyzerError('method: %s, result: %s' % (
        method, ast_node_list))
    ast_node = ast_node_list[0]
    return ast_node_list

  def default_analyze_node(self, pnode):
    #print "default_analyze_node", type(pnode)
    return [pnode.copy()]

  # some nodes just don't need analysis
  def skip_analyze_node(self, pnode):
    return [pnode.copy()]
  analyzeIdentifierNode = skip_analyze_node
  analyzeLiteralNode = skip_analyze_node

  def analyzeTemplateNode(self, pnode):
    self.template = pnode.copy(copy_children=False)
    self.template.classname = self.classname
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      self.template.main_function.extend(self.build_ast(pn))

    self.template.main_function = self.build_ast(self.template.main_function)[0]
    return [self.template]

  def analyzeForNode(self, pnode):
    for_node = ForNode()

    for pn in pnode.target_list.child_nodes:
      for_node.target_list.extend(self.build_ast(pn))
    for pn in pnode.expression_list.child_nodes:
      for_node.expression_list.extend(self.build_ast(pn))
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      for_node.extend(self.build_ast(pn))
      
    return [for_node]

  def analyzeGetUDNNode(self, pnode):
    expression = self.build_ast(pnode.expression)[0]
    get_udn_node = GetUDNNode(expression, pnode.name)
    return [get_udn_node]

  def analyzeGetAttrNode(self, pnode):
    expression = self.build_ast(pnode.expression)[0]
    get_attr_node = GetAttrNode(expression, pnode.name)
    return [get_attr_node]

  def analyzeIfNode(self, pnode):
    if_node = IfNode()
    if_node.test_expression = self.build_ast(pnode.test_expression)[0]
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      if_node.extend(self.build_ast(pn))
    for pn in self.optimize_parsed_nodes(pnode.else_):
      if_node.else_.extend(self.build_ast(pn))
    return [if_node]

  def analyzeArgListNode(self, pnode):
    list_node = ArgListNode()
    for n in pnode:
      list_node.extend(self.build_ast(n))
    return [list_node]

  def analyzeParameterNode(self, pnode):
    param = pnode.copy()
    param.default = self.build_ast(pnode.default)[0]
    return [param]

  def analyzeSliceNode(self, pnode):
    snode = pnode.copy()
    snode.expression = self.build_ast(pnode.expression)[0]
    snode.slice_expression = self.build_ast(pnode.slice_expression)[0]
    return [snode]

  # FIXME: should I move this to a directive?
  def analyzeImplementsNode(self, pnode):
    if pnode.name == 'library':
      self.template.library = True
    else:
      self.template.main_function.name = pnode.name      
    return []

  def analyzeImportNode(self, pnode):
    node = ImportNode([self.build_ast(n)[0] for n in pnode.module_name_list])
    self.template.import_nodes.append(node)
    return []

  def analyzeExtendsNode(self, pnode):
    self.analyzeImportNode(pnode)

    # actually want to reference the class within the module name
    pnode = copy.deepcopy(pnode)
    pnode.module_name_list.append(pnode.module_name_list[-1])
    self.template.extends_nodes.append(pnode)
    return []

  def analyzeFromNode(self, pnode):
    self.template.from_nodes.append(pnode.copy())
    return []

  def analyzeTextNode(self, pnode):
    if pnode.child_nodes:
      raise SemanticAnalyzerError("TextNode can't have children")
    f = CallFunctionNode(GetAttrNode(IdentifierNode('buffer'), 'write'))
    f.arg_list.append(LiteralNode(pnode.value))
    return [f]

  analyzeOptionalWhitespaceNode = analyzeTextNode
  analyzeWhitespaceNode = analyzeTextNode
  analyzeNewlineNode = analyzeTextNode

  # purely here for passthru and to remind me that it needs to be overridden
  def analyzeFunctionNode(self, pnode):
    return [pnode]

  def analyzeDefNode(self, pnode):
    #if not pnode.child_nodes:
    #  raise SemanticAnalyzerError("DefNode must have children")
    function = FunctionNode(pnode.name)
    if pnode.parameter_list:
      function.parameter_list = self.build_ast(pnode.parameter_list)[0]

    function.parameter_list.child_nodes.insert(0,
                                               ParameterNode(name='self'))
    
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      function.extend(self.build_ast(pn))

    function = self.build_ast(function)[0]
    self.template.append(function)
    return []

  def analyzeAttributeNode(self, pnode):
    self.template.attr_nodes.append(pnode.copy())
    return []

  def analyzeBlockNode(self, pnode):
    #if not pnode.child_nodes:
    #  raise SemanticAnalyzerError("BlockNode must have children")
    self.analyzeDefNode(pnode)
    function_node = CallFunctionNode()
    function_node.expression = self.build_ast(PlaceholderNode(pnode.name))[0]
    p = PlaceholderSubstitutionNode(function_node)
    #print "analyzeBlockNode", id(p), p
    return self.build_ast(p)

  # note: we do a copy-thru to force analysis of the child nodes
  def analyzePlaceholderSubstitutionNode(self, pnode):
    #print "analyzePlaceholderSubstitutionNode", id(pnode), pnode
    f = CallFunctionNode(GetAttrNode(IdentifierNode('buffer'), 'write'))
    f.arg_list.append(BinOpNode('%', LiteralNode('%s'),
                                self.build_ast(pnode.expression)[0]))
    return self.build_ast(f)

  def analyzePlaceholderNode(self, pnode):
    f = CallFunctionNode(GetAttrNode(IdentifierNode('self'),
                                     'resolve_placeholder'))
    f.arg_list.append(LiteralNode(pnode.name))
    f.arg_list.append(t_local_vars())
    f.arg_list.append(t_global_vars())
    f.hint_map['resolve_placeholder'] = IdentifierNode(pnode.name)
    return self.build_ast(f)

  def analyzeBinOpNode(self, pnode):
    n = pnode.copy()
    n.left = self.build_ast(n.left)[0]
    n.right = self.build_ast(n.right)[0]
    return [n]

  analyzeBinOpExpressionNode = analyzeBinOpNode
  
  def analyzeUnaryOpNode(self, pnode):
    n = pnode.copy()
    n.expression = self.build_ast(n.expression)[0]
    return [n]

  def analyzeCommentNode(self, pnode):
    return []

  def analyzeCallFunctionNode(self, pnode):
    # print "analyzeCallFunctionNode", pnode.expression.name
    fn = pnode.copy()
    # fixme: the problem here is that this means that some fallout
    # from python code generation is percolating into the semantic
    # analysis phase. i think that's wrong - but i'm not 100% sure
    if (isinstance(fn.expression, PlaceholderNode) and
        fn.expression.name in ('get_var', 'has_var')):
      # fixme: total cheat here
      fn.arg_list.append(t_local_vars())
      fn.arg_list.append(t_global_vars())
    fn.expression = self.build_ast(fn.expression)[0]
    fn.arg_list = self.build_ast(fn.arg_list)[0]
    return [fn]

  # go over the parsed nodes and weed out the parts we don't need
  # it's easier to do this before we morph the AST to look more like python
  def optimize_parsed_nodes(self, node_list):
    optimized_nodes = []
    for n in node_list:
      # strip optional whitespace by removing the nodes
      if (self.options.strip_optional_whitespace and
          isinstance(n, OptionalWhitespaceNode)):
        continue
      # collapse adjacent TextNodes so we are calling these buffer writes
      elif (self.options.collapse_adjacent_text and
            isinstance(n, TextNode) and
            len(optimized_nodes) and
            isinstance(optimized_nodes[-1], TextNode)):
        optimized_nodes[-1].append_text_node(n)
      else:
        optimized_nodes.append(n)
    #print "optimized_nodes", node_list, optimized_nodes
    return optimized_nodes


# template objects for certain common subcomponents
def t_local_vars():
  t = ParameterNode('local_vars',
                    CallFunctionNode(IdentifierNode('locals')))
  return t

def t_global_vars():
  t = ParameterNode('global_vars',
                    CallFunctionNode(IdentifierNode('globals')))
  return t
