import copy
import logging
import os.path

from spitfire.compiler.ast import *
from spitfire.compiler.analyzer import *
from spitfire.compiler.visitor import print_tree

import __builtin__
builtin_names = vars(__builtin__)


class _BaseAnalyzer(object):
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
    if method_name in self.compiler.debug_flags:
      print method_name, node
    return method(node)

  def skip_analyze_node(self, node):
    return
  analyzeLiteralNode = skip_analyze_node
  analyzeIdentifierNode = skip_analyze_node
  analyzeTargetNode = skip_analyze_node
  
  def default_optimize_node(self, node):
    # print "default_optimize_node", type(node)
    self.unoptimized_node_types.add(type(node))
    return

  def get_parent_loop(self, node):
    return self._get_parent_node_by_type(node, ForNode)
  
  def get_parent_function(self, node):
    return self._get_parent_node_by_type(node, FunctionNode)

  def get_parent_block(self, node):
    return self._get_parent_node_by_type(node,
      (FunctionNode, ForNode, IfNode, ElseNode))

  def _get_parent_node_by_type(self, node, node_type):
    node = node.parent
    while node is not None:
      if isinstance(node, node_type):
        return node
      node = node.parent
    return None

  # this function has some rules that are a bit unclean - you aren't actually
  # looking for the 'parent' scope, but one you might insert nodes into.
  # for instance, you skip over a ForNode so that optimizetions are inserted
  # in a loop-invariant fashion.
  def get_parent_scope(self, node):
    node_stack = [node]
    node = node.parent
    while node is not None:
      if type(node) == FunctionNode:
        return node.scope
      elif type(node) == IfNode:
        # elements of the test clause need to reference the next scope
        # "up" - usually the function, but could be another conditional block
        # fixme: if we ever implement "elif" this will have to get fixed up
        if node_stack[-1] != node.test_expression:
          return node.scope
      elif type(node) == ElseNode:
        return node.scope
      elif type(node) == ForNode:
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


  def reanalyzeConditionalNode(self, conditional_node):
    if not self.options.hoist_conditional_aliases:
      return

    parent_block, insertion_point = self.get_insert_block_and_point(conditional_node)
    
    # print "reanalyzeConditionalNode", conditional_node
    # print "parent_block", parent_block
    # print "parent_scope", parent_block.scope
    for alias_node, alias in conditional_node.scope.aliased_expression_map.iteritems():
      assign_alias = AssignNode(alias, alias_node)
      if alias_node in parent_block.scope.aliased_expression_map:
        # prune the implementation in the nested block
        # print "prune", alias_node
        # print "parent_block aliases", parent_block.scope.aliased_expression_map
        conditional_node.child_nodes.remove(assign_alias)
        # if we've already hoisted an assignment, don't do it again
        if alias_node not in parent_block.scope.hoisted_aliases:
          # prune the original implementation in the current block and
          # reinsert the alias before it's first potential usage if it
          # is needed earlier in the execution path.
          # when a variable aliased in both the if and
          # else blocks is promoted to the parent scope
          # the implementation isn't actually hoisted (should it be?)
          # inline with the IfNode optimization so we need to check if the
          # node is already here
          if assign_alias in parent_block.child_nodes:
            current_pos = parent_block.child_nodes.index(assign_alias)
            # an else node's parent is the IfNode, which is the relevant
            # node when searching for the insertion point
            needed_pos = parent_block.child_nodes.index(insertion_point)
            if needed_pos < current_pos:
              parent_block.child_nodes.remove(assign_alias)
              parent_block.insert_before(conditional_node, assign_alias)
              # print "insert_before", alias_node
          else:
            # still need to insert the alias
            parent_block.insert_before(conditional_node, assign_alias)
          parent_block.scope.hoisted_aliases.append(alias_node)

  # FIXME: refactor out the common code from reanalyzeConditionalNode
  def reanalyzeLoopNode(self, loop_node):
    if not self.options.hoist_loop_invariant_aliases:
      return
    parent_block, insertion_point = self.get_insert_block_and_point(loop_node)
    
    for alias_node, alias in loop_node.scope.aliased_expression_map.iteritems():
      assign_alias = AssignNode(alias, alias_node)
      if alias_node in parent_block.scope.aliased_expression_map:
        # prune the implementation in the nested block
        # print "prune", alias_node
        # print "parent_block aliases", parent_block.scope.aliased_expression_map
        loop_node.child_nodes.remove(assign_alias)
        # if we've already hoisted an assignment, don't do it again
        if alias_node not in parent_block.scope.hoisted_aliases:
          # prune the original implementation in the current block and
          # reinsert the alias before it's first potential usage if it
          # is needed earlier in the execution path.
          # when a variable aliased in both the if and
          # else blocks is promoted to the parent scope
          # the implementation isn't actually hoisted (should it be?)
          # inline with the IfNode optimization so we need to check if the
          # node is already here
          if assign_alias in parent_block.child_nodes:
            current_pos = parent_block.child_nodes.index(assign_alias)
            # an else node's parent is the IfNode, which is the relevant
            # node when searching for the insertion point
            needed_pos = parent_block.child_nodes.index(insertion_point)
            if needed_pos < current_pos:
              parent_block.child_nodes.remove(assign_alias)
              parent_block.insert_before(loop_node, assign_alias)
              #print "insert_before", alias_node
          else:
            # still need to insert the alias
            parent_block.insert_before(loop_node, assign_alias)
          parent_block.scope.hoisted_aliases.append(alias_node)
      else:
        # if this alias is not already used in the parent scope, that's
        # ok, hoist it if it's loop invariant
        # fixme: stronger check for invariance - right now it's not really
        # possible to be look-variant - we treat loop variables as placeholders
        # so we are calling resolve_udn, which doesn't get aliased
        loop_node.child_nodes.remove(assign_alias)
        parent_block.insert_before(loop_node, assign_alias)
        parent_block.scope.hoisted_aliases.append(alias_node)
        

class OptimizationAnalyzer(_BaseAnalyzer):
  def analyzeParameterNode(self, parameter):
    self.visit_ast(parameter.default, parameter)
    return
  
  def analyzeTemplateNode(self, template):
    for n in template.from_nodes:
      if n.alias:
        template.global_identifiers.add(n.alias)
      else:
        template.global_identifiers.add(n.identifier)
      
    self.visit_ast(template.main_function, template)
    for n in template.child_nodes:
      self.visit_ast(n, template)

  def analyzeFunctionNode(self, function):
    function.scope.local_identifiers.extend([IdentifierNode(n.name)
                                             for n in function.parameter_list])
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

  def analyzeTupleLiteralNode(self, tuple_literal_node):
    for n in tuple_literal_node.child_nodes:
      self.visit_ast(n, tuple_literal_node)

  def analyzeCallFunctionNode(self, function_call):
    self.visit_ast(function_call.expression, function_call)
    self.visit_ast(function_call.arg_list, function_call)

  def analyzePlaceholderNode(self, placeholder):
    if self.options.directly_access_defined_variables:
      # when the analyzer finds a PlaceholderNode and generates a function
      # call out of it, i annotate an IdentifierNode with the original
      # placeholder name
      local_var = IdentifierNode(placeholder.name)
      cached_placeholder = IdentifierNode('_rph_%s' % local_var.name)
      local_identifiers = self.get_local_identifiers(placeholder)
      #print "local_identifiers", local_identifiers
      if local_var in local_identifiers:
        placeholder.parent.replace(placeholder, local_var)
      elif local_var in self.ast_root.global_identifiers:
        placeholder.parent.replace(placeholder, local_var)
      elif cached_placeholder in local_identifiers:
        placeholder.parent.replace(placeholder, cached_placeholder)
      elif local_var.name in builtin_names:
        placeholder.parent.replace(placeholder,
                                   IdentifierNode(local_var.name))
      elif self.options.cache_resolved_placeholders:
        insert_block, insert_marker = self.get_insert_block_and_point(
          placeholder)
        # note: this is sketchy enough that it requires some explanation
        # basically, you need to visit the node for the parent function to
        # get the memo that this value is aliased. unfortunately, the naive
        # case of just calling visit_ast blows up since it tries to double
        # analyze a certain set of nodes. you only really need to analyze
        # that the assignment took place, then you can safely alias the
        # actual function call. definitely sketchy, but it does seem to work
        assign_rph = AssignNode(cached_placeholder, None)
        #print "optimize scope:", insert_block
        #print "optimize marker:", insert_marker
        insert_block.insert_before(
          insert_marker, assign_rph)
        self.visit_ast(assign_rph, insert_block)
        assign_rph.right = placeholder
        placeholder.parent.replace(placeholder, cached_placeholder)    
      
  def analyzePlaceholderSubstitutionNode(self, placeholder_substitution):
    self.visit_ast(placeholder_substitution.expression,
                   placeholder_substitution)

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
      #print "analyzeGetAttrNode", scope, alias
      if node.expression.name[0] != '_':
        alias_format = '_%s_%s'
      else:
        alias_format = '%s_%s'
      alias_name = alias_format % (node.expression.name, node.name)
      if alias_name in scope.alias_name_set:
        print "duplicate alias_name", alias_name
        print "scope", scope
        print "scope.alias_name_set", scope.alias_name_set
        print "scope.aliased_expression_map", scope.aliased_expression_map
        return
      
      alias = IdentifierNode(alias_name)
      scope.alias_name_set.add(alias_name)
      scope.aliased_expression_map[node] = alias
      assign_alias = AssignNode(alias, node)
      
      parent_loop = self.get_parent_loop(node)
      # fixme: check to see if this expression is loop-invariant
      # must add a test case for this
      child_node_set = set(node.getChildNodes())
      #print "child_node_set", child_node_set
      #print "parent_loop", parent_loop, "parent", node.parent
      if (self.options.inline_hoist_loop_invariant_aliases and
          parent_loop is not None and
          not parent_loop.loop_variant_set.intersection(child_node_set)):
        # print "pull up loop invariant", assign_alias
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

    parent_scope = self.get_parent_scope(if_node)
    
    # once both branches are optimized, walk the scopes for any variables that
    # are defined in both places. those will be promoted to function scope
    # since it is safe to assume that those will defined
    # fixme: this feels like a bit of hack - but not sure how to do this
    # correctly without reverting to slower performance for almost all calls to
    # resolve_placeholder.
    #
    # it seems like certain optimizations need
    # to be hoisted up to the parent scope. this is particularly the case when
    # you are aliasing common functions that are likely to occur in the parent
    # scope after the conditional block. you *need* to hoist those, or you will
    # have errors when the branch fails. essentially you have to detect and
    # hoist 'branch invariant' optimizations.
    if if_node.else_.child_nodes:
      if_scope_vars = set(if_node.scope.local_identifiers)
      common_local_identifiers = list(if_scope_vars.intersection(
        if_node.else_.scope.local_identifiers))
      common_alias_name_set = if_node.scope.alias_name_set.union(
        if_node.else_.scope.alias_name_set)
      common_aliased_expression_map = {}
      for key, val in if_node.scope.aliased_expression_map.iteritems():
        if key in if_node.else_.scope.aliased_expression_map:
          common_aliased_expression_map[key] = val

      parent_scope.local_identifiers.extend(common_local_identifiers)
      parent_scope.alias_name_set.update(common_alias_name_set)
      parent_scope.aliased_expression_map.update(common_aliased_expression_map)
    else:
      # we can try to hoist up invariants if they don't depend on the
      # condition. this is somewhat hard to know, so the best way to do so
      # without multiple passes of the optimizer is to hoist only things that
      # were already defined in the parent scope - like _buffer, or things on
      # self.
      pass
      
#     else:
#       common_local_identifiers = if_node.scope.local_identifiers
#       common_alias_name_set = if_node.scope.alias_name_set
#       common_aliased_expression_map = if_node.scope.aliased_expression_map
      
#     scope = self.get_parent_scope(if_node)
#     scope.local_identifiers.extend(common_local_identifiers)
#     scope.alias_name_set.update(common_alias_name_set)
#     scope.aliased_expression_map.update(common_aliased_expression_map)

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
        local_identifiers.extend(node.scope.local_identifiers)
      elif isinstance(node, FunctionNode):
        local_identifiers.extend(node.scope.local_identifiers)
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


# a second pass over the optimized tree to hoist invariant aliases to their
# parent blocks
class FinalPassAnalyzer(_BaseAnalyzer):
  def analyzeTemplateNode(self, template):
    self.visit_ast(template.main_function, template)
    for n in template.child_nodes:
      self.visit_ast(n, template)

  def analyzeFunctionNode(self, function):
    for n in function.child_nodes:
      self.visit_ast(n, function)

  def analyzeForNode(self, for_node):
    for n in for_node.child_nodes:
      self.visit_ast(n, for_node)

    self.reanalyzeLoopNode(for_node)

  def analyzeIfNode(self, if_node):
    # depth-first
    for n in if_node.child_nodes:
      self.visit_ast(n, if_node)

    for n in if_node.else_.child_nodes:
      self.visit_ast(n, if_node.else_)


    self.reanalyzeConditionalNode(if_node)
    self.reanalyzeConditionalNode(if_node.else_)

