import copy
import os.path

from spitfire.compiler.ast import *
from spitfire.compiler.analyzer import *


class OptimizationAnalyzer(object):
  def __init__(self, ast_root, options=default_options):
    self.ast_root = ast_root
    self.options = options
    self.unoptimized_node_types = set()
    
  def optimize_ast(self):
    self.visit_ast(self.ast_root)
    if self.options.debug:
      print "unoptimized_node_types", self.unoptimized_node_types
    return self.ast_root

  # build an AST node list from a single parse node
  # need the parent in case we are going to delete a node
  def visit_ast(self, node, parent=None):
    node.parent = parent
    method_name = 'analyze%s' % node.__class__.__name__
    method = getattr(self, method_name, self.default_optimize_node)
    return method(node)

  def skip_analyze_node(self, node):
    return
  analyzeLiteralNode = skip_analyze_node
  analyzeIdentifierNode = skip_analyze_node
  analyzeTargetNode = skip_analyze_node
  
  def default_optimize_node(self, node):
    #print "default_optimize_node", type(node)
    self.unoptimized_node_types.add(type(node))
    return
  
  def analyzeTemplateNode(self, template):
    self.visit_ast(template.main_function, template)
    for n in template.child_nodes:
      self.visit_ast(n, template)

  def analyzeFunctionNode(self, function):
    function.aliased_expression_map = {}
    function.alias_name_set = set()
    for n in function.child_nodes:
      self.visit_ast(n, function)

  def analyzeForNode(self, for_node):
    self.visit_ast(for_node.target_list, for_node)
    for_node.loop_variant_set = set(for_node.target_list.flat_list)
    self.visit_ast(for_node.expression_list, for_node)
    for n in for_node.child_nodes:
      self.visit_ast(n, for_node)

  def analyzeExpressionListNode(self, expression_list_node):
    for n in expression_list_node:
      self.visit_ast(n, expression_list_node)

  def analyzeTargetListNode(self, target_list_node):
    flat_list = []
    for n in target_list_node:
      self.visit_ast(n, target_list_node)
      if type(n) == TargetListNode:
        flat_list.extend(n.flat_list)
      else:
        flat_list.append(n)
    target_list_node.flat_list = flat_list

  def analyzeArgListNode(self, arg_list_node):
    for n in arg_list_node:
      self.visit_ast(n, arg_list_node)

  def analyzeCallFunctionNode(self, function_call):
    self.visit_ast(function_call.expression, function_call)
    self.visit_ast(function_call.arg_list, function_call)
    if self.options.directly_access_defined_variables:
      try:
        local_var = function_call.hint_map['resolve_placeholder']
        local_identifiers = self.get_local_identifiers(function_call)
        if local_var in local_identifiers:
          function_call.parent.replace(function_call, local_var)
      except KeyError:
        pass
      
  def get_parent_loop(self, node):
    node = node.parent
    while node is not None:
      if type(node) == ForNode:
        return node
      node = node.parent
    return None

  def get_parent_function(self, node):
    node = node.parent
    while node is not None:
      if type(node) == FunctionNode:
        return node
      node = node.parent
    raise SemanticAnalyzerError("expected a parent function")

  def get_insert_block_and_point(self, node):
    insert_marker = node
    node = node.parent
    while node is not None:
      if isinstance(node, (FunctionNode, ForNode, IfNode)):
        return node, insert_marker
      insert_marker = node
      node = node.parent
    raise SemanticAnalyzerError("expected a parent block")

  def replace_in_parent_block(self, node, new_node):
    insert_block, insert_marker = self.get_insert_block_and_point(node)
    insert_block.replace(insert_marker, new_node)

  def analyzeGetAttrNode(self, node):
    if not self.options.alias_invariants:
      return
    
    # fixme; only handle the trivial case for now
    # simplifies the protocol for making up alias names
    if type(node.expression) != IdentifierNode:
      return
    
    function = self.get_parent_function(node)
    alias = function.aliased_expression_map.get(node)
    if not alias:
      alias_name = '_%s_%s' % (node.expression.name, node.name)
      if alias_name in function.alias_name_set:
        print "duplicate alias_name", alias_name
        return
      
      alias = IdentifierNode(alias_name)
      function.aliased_expression_map[node] = alias
      assign_alias = AssignNode(alias, node)
      parent_loop = self.get_parent_loop(node)
      # fixme: check to see if this expression is loop-invariant
      # must add a test case for this
      child_node_set = set(node.getChildNodes())
      #print "child_node_set", child_node_set
      #print "parent_loop", parent_loop, "parent", node.parent
      if (parent_loop is not None and
          not parent_loop.loop_variant_set.intersection(child_node_set)):
        #print "pull up loop invariant", assign_alias
        parent_loop.parent.insert_before(parent_loop, assign_alias)
      else:
        insert_block, insert_marker = self.get_insert_block_and_point(node)
        insert_block.insert_before(insert_marker, assign_alias)

    node.parent.replace(node, alias)
      

  def analyzeIfNode(self, if_node):
    self.visit_ast(if_node.test_expression, if_node)
    for n in if_node.child_nodes:
      self.visit_ast(n, if_node)
    for n in if_node.else_:
      self.visit_ast(n, if_node)

  def analyzeBinOpNode(self, n):
    self.visit_ast(n.left, n)
    self.visit_ast(n.right, n)

  analyzeBinOpExpressionNode = analyzeBinOpNode

  def get_local_identifiers(self, node):
    local_identifiers = []
    node = node.parent
    while node is not None and not isinstance(node, FunctionNode):
      # fixme: there are many more sources of local_identifiers
      # have to scan AssignNodes up to your current position
      # also check the parameters of your function
      if isinstance(node, ForNode):
        local_identifiers.extend(node.loop_variant_set)
      node = node.parent
    return local_identifiers
  
  def analyzeGetUDNNode(self, node):
    self.visit_ast(node.expression, node)


#   def analyzeSliceNode(self, pnode):
#     snode = pnode
#     snode.expression = self.build_ast(pnode.expression)[0]
#     snode.slice_expression = self.build_ast(pnode.slice_expression)[0]
#     return [snode]

#   def analyzeAttributeNode(self, pnode):
#     self.template.attr_nodes.append(pnode.copy())
#     return []

  
#   def analyzeUnaryOpNode(self, pnode):
#     n = pnode.copy()
#     n.expression = self.build_ast(n.expression)[0]
#     return [n]
