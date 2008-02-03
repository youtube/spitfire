import copy
import os.path

from spitfire.compiler.ast import *
from spitfire.compiler.analyzer import *

import __builtin__
builtin_names = vars(__builtin__)


class OptimizationAnalyzer(object):
  def __init__(self, ast_root, options, compiler):
    self.ast_root = ast_root
    self.options = options
    self.compiler = compiler
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
  an3alyzeTargetNode = skip_analyze_node
  
  def default_optimize_node(self, node):
    # print "default_optimize_node", type(node)
    self.unoptimized_node_types.add(type(node))
    return

  def analyzeParameterNode(self, parameter):
    self.visit_ast(parameter.default, parameter)
    return
  
  def analyzeTemplateNode(self, template):
    self.visit_ast(template.main_function, template)
    for n in template.child_nodes:
      self.visit_ast(n, template)

  def analyzeFunctionNode(self, function):
    function.aliased_expression_map = {}
    function.alias_name_set = set()
    function.local_identifiers = [IdentifierNode(n.name)
                                  for n in function.parameter_list]
    for n in function.child_nodes:
      self.visit_ast(n, function)

  def analyzeForNode(self, for_node):
    self.visit_ast(for_node.target_list, for_node)
    for_node.loop_variant_set = set(for_node.target_list.flat_list)
    self.visit_ast(for_node.expression_list, for_node)
    for n in for_node.child_nodes:
      self.visit_ast(n, for_node)

  def analyzeAssignNode(self, node):
    _identifier = IdentifierNode(node.left.name)
    scope = self.get_parent_scope(node)
    scope.local_identifiers.append(_identifier)
    # note: this hack is here so you can partially analyze alias nodes
    # without double-processing
    if node.right:
      self.visit_ast(node.right, node)

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

#   def analyzeParameterListNode(self, parameter_list_node):
#     flat_list = []
#     for n in parameter_list_node:
#       flat_list.append(n)
#     target_list_node.flat_list = flat_list

  def analyzeArgListNode(self, arg_list_node):
    for n in arg_list_node:
      self.visit_ast(n, arg_list_node)

  def analyzeCallFunctionNode(self, function_call):
    self.visit_ast(function_call.expression, function_call)
    self.visit_ast(function_call.arg_list, function_call)
    if self.options.directly_access_defined_variables:
      # when the analyzer finds a PlaceholderNode and generates a function
      # call out of it, i annotate an IdentifierNode with the original
      # placeholder name
      local_var = function_call.hint_map.get('resolve_placeholder', None)
      if local_var is not None:
        cached_placeholder = IdentifierNode('_rph_%s' % local_var.name)
        local_identifiers = self.get_local_identifiers(function_call)
        # print "local_identifiers", local_identifiers
        if local_var in local_identifiers:
          function_call.parent.replace(function_call, local_var)
        elif cached_placeholder in local_identifiers:
          function_call.parent.replace(function_call, cached_placeholder)
        elif local_var.name in builtin_names:
          function_call.parent.replace(function_call,
                                       IdentifierNode(local_var.name))
        elif self.options.cache_resolved_placeholders:
          insert_scope, insert_marker = self.get_insert_block_and_point(
            function_call)
          # note: this is sketchy enough that it requires some explanation
          # basically, you need to visit the node for the parent function to
          # get the memo that this value is aliased. unfortunately, the naive
          # case of just calling visit_ast blows up since it tries to double
          # analyze a certain set of nodes. you only really need to analyze
          # that the assignment took place, then you can safely alias the
          # actual function call. definitely sketchy, but it does seem to work
          assign_rph = AssignNode(cached_placeholder, None)
          #print "optimize scope:", insert_scope
          #print "optimize marker:", insert_marker
          insert_scope.insert_before(
            insert_marker, assign_rph)
          self.visit_ast(assign_rph, insert_scope)
          assign_rph.right = function_call
          function_call.parent.replace(function_call, cached_placeholder)
      
  def analyzePlaceholderSubstitutionNode(self, placeholder_substitution):
    self.visit_ast(placeholder_substitution.expression,
                   placeholder_substitution)

  def get_parent_loop(self, node):
    node = node.parent
    while node is not None:
      if type(node) == ForNode:
        return node
      node = node.parent
    return None

  def get_parent_scope(self, node):
    node_stack = [node]
    node = node.parent
    while node is not None:
      if type(node) == FunctionNode:
        return node
      elif type(node) == IfNode:
        # elements of the test clause need to reference the next scope
        # "up" - usually the function
        # fixme: if we ever implement "elif" this will have to get fixed up
        if node_stack[-1] != node.test_expression:
          return node.scope
      elif type(node) == ElseNode:
        return node.scope
      node_stack.append(node)
      node = node.parent
    raise SemanticAnalyzerError("expected a parent function")

  def get_insert_block_and_point(self, node):
    original_node = node
    insert_marker = node
    node = node.parent
    while node is not None:
      if isinstance(node, (FunctionNode, ForNode, IfNode, ElseNode)):
        if insert_marker in node.child_nodes:
          return node, insert_marker
          
      insert_marker = node
      node = node.parent
    raise SemanticAnalyzerError("expected a parent block")

  def replace_in_parent_block(self, node, new_node):
    insert_block, insert_marker = self.get_insert_block_and_point(node)
    insert_block.replace(insert_marker, new_node)

#   def alias_expression_in_function(self, function, expression):
#     alias = function.aliased_expression_map.get(expression)
#     if not alias:
#       alias_name = '_%s' % (expression.name)
#       if alias_name in function.alias_name_set:
#         print "duplicate alias_name", alias_name
#         return
      
#       alias = IdentifierNode(alias_name)
#       function.aliased_expression_map[expression] = alias
#       assign_alias = AssignNode(alias, expression)
#       parent_loop = self.get_parent_loop(node)
#       # fixme: check to see if this expression is loop-invariant
#       # must add a test case for this
#       child_node_set = set(node.getChildNodes())
#       #print "child_node_set", child_node_set
#       #print "parent_loop", parent_loop, "parent", node.parent
#       if (parent_loop is not None and
#           not parent_loop.loop_variant_set.intersection(child_node_set)):
#         #print "pull up loop invariant", assign_alias
#         parent_loop.parent.insert_before(parent_loop, assign_alias)
#       else:
#         insert_block, insert_marker = self.get_insert_block_and_point(node)
#         insert_block.insert_before(insert_marker, assign_alias)

#     node.parent.replace(node, alias)
    

  def analyzeGetAttrNode(self, node):
    if not self.options.alias_invariants:
      return
    
    # fixme: only handle the trivial case for now
    # simplifies the protocol for making up alias names
    if type(node.expression) != IdentifierNode:
      return
    
    scope = self.get_parent_scope(node)
    alias = scope.aliased_expression_map.get(node)
    if not alias:
      if node.expression.name[0] != '_':
        alias_format = '_%s_%s'
      else:
        alias_format = '%s_%s'
      alias_name = alias_format % (node.expression.name, node.name)
      if alias_name in scope.alias_name_set:
        print "duplicate alias_name", alias_name
        return
      
      alias = IdentifierNode(alias_name)
      scope.aliased_expression_map[node] = alias
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

    for n in if_node.else_.child_nodes:
      self.visit_ast(n, if_node.else_)

  def analyzeBinOpNode(self, n):
    self.visit_ast(n.left, n)
    self.visit_ast(n.right, n)

  analyzeBinOpExpressionNode = analyzeBinOpNode

  def analyzeUnaryOpNode(self, op_node):
    self.visit_ast(op_node.expression, op_node)

  def get_local_identifiers(self, node):
    local_identifiers = []
#     # search over the previous siblings for this node
#     # mostly to look for AssignNode
#     if node.parent is not None:
#       idx = node.parent.child_nodes.index(node)
#       previous_siblings = node.parent.child_nodes[:idx]
      
    
    # search the parent scopes
    # fixme: looking likely that this should be recursive
    node = node.parent
    while node is not None:
      # fixme: there are many more sources of local_identifiers
      # have to scan AssignNodes up to your current position
      # also check the parameters of your function
      if isinstance(node, ForNode):
        local_identifiers.extend(node.loop_variant_set)
      elif isinstance(node, FunctionNode):
        local_identifiers.extend(node.local_identifiers)
        break
      node = node.parent
    return frozenset(local_identifiers)
  
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
