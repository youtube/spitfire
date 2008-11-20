import copy
import logging
import os.path
import re

from spitfire.compiler.ast import *
from spitfire.compiler.analyzer import *
from spitfire.compiler.visitor import print_tree
from spitfire.compiler.walker import flatten_tree

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
        if node_stack[-1] != node.expression_list:
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
    if (not self.options.hoist_conditional_aliases and
        not self.options.cache_filtered_placeholders):
      return

    parent_node = conditional_node
    parent_block, insertion_point = self.get_insert_block_and_point(
      conditional_node)

    if self.options.hoist_conditional_aliases:
      #print "reanalyzeConditionalNode", conditional_node
      #print "  parent_block", parent_block
      #print "  parent_scope", parent_block.scope
      # NOTE: need to iterate over items, in case we modify something
      for alias_node, alias in conditional_node.scope.aliased_expression_map.items():
        #print "  check alias:", alias
        #print "    alias_node:", alias_node
        assign_alias_node = AssignNode(alias, alias_node)
        if alias_node in parent_block.scope.aliased_expression_map:
          if self.is_condition_invariant(alias_node, conditional_node):
            #print "  hoist:", assign_alias_node
            self.hoist(
              conditional_node, parent_block, insertion_point, alias_node,
              assign_alias_node)

          
  def reanalyzeLoopNode(self, loop_node):
    if not self.options.hoist_loop_invariant_aliases:
      return

    parent_block, insertion_point = self.get_insert_block_and_point(loop_node)
    # NOTE: need to iterate over items, in case we modify something
    for alias_node, alias in loop_node.scope.aliased_expression_map.items():
      assign_alias = AssignNode(alias, alias_node)
      if alias_node in parent_block.scope.aliased_expression_map:
        if self.is_loop_invariant(alias_node, loop_node):
          self.hoist(loop_node, parent_block, insertion_point, alias_node,
                     assign_alias)
      else:
        # if this alias is not already used in the parent scope, that's
        # ok, hoist it if it's loop invariant
        if self.is_loop_invariant(alias_node, loop_node):
          loop_node.remove(assign_alias)
          parent_block.insert_before(loop_node, assign_alias)
          parent_block.scope.hoisted_aliases.append(alias_node)

  def is_condition_invariant(self, node, conditional_node):
    node_dependency_set = self.get_node_dependencies(node)
    condition_invariant = not node_dependency_set.intersection(
      conditional_node.scope.local_identifiers)
    #print "is_condition_invariant:", condition_invariant
    #print "  locals:", conditional_node.scope.local_identifiers
    #print "  deps:", node_dependency_set
    return condition_invariant

  def is_loop_invariant(self, node, loop_node):
    node_dependency_set = self.get_node_dependencies(node)
#     print "is loop invariant node:", node
#     for x in node_dependency_set:
#       print "  dep:", x
    return not loop_node.loop_variant_set.intersection(node_dependency_set)

  def get_node_dependencies(self, node):
    node_dependency_set = set(flatten_tree(node))
    parent_block = self.get_parent_block(node)

    for n in list(node_dependency_set):
      # when this is an identifier, you need to check all of the potential
      # the dependencies for that symbol, which means doing some crawling
      if isinstance(n, IdentifierNode):
        identifier = n
        parent_block_to_check = parent_block
        while parent_block_to_check:
          for block_node in parent_block_to_check.child_nodes:
            if isinstance(block_node, AssignNode):
              if block_node.left == identifier:
                node_dependency_set.update(
                  self.get_node_dependencies(block_node.right))
                parent_block_to_check = None
                break
          else:
            parent_block_to_check = self.get_parent_block(
              parent_block_to_check)
      #elif isinstance(n, (GetUDNNode, FilterNode)):
      #  node_dependency_set.update(
      #    self.get_node_dependencies(node.expression))
    #print "get_node_dependencies", node
    #print "  deps:", node_dependency_set
    return node_dependency_set


class OptimizationAnalyzer(_BaseAnalyzer):
  def analyzeParameterNode(self, parameter):
    self.visit_ast(parameter.default, parameter)
    return
  
  def analyzeTemplateNode(self, template):
    # at this point, if we have a function registry, add in the nodes before we
    # begin optimizing
    for alias, (fq_name, method) in self.compiler.function_name_registry.iteritems():
      fq_name_parts = fq_name.split('.')
      self.ast_root.from_nodes.append(FromNode(
        [IdentifierNode(x) for x in fq_name_parts[:-1]],
        IdentifierNode(fq_name_parts[-1]),
        IdentifierNode(alias)))
      
    for n in template.from_nodes:
      if n.alias:
        template.global_identifiers.add(n.alias)
      else:
        template.global_identifiers.add(n.identifier)

    # scan extends for dependencies
    # this allows faster calling of template functions - we could also
    # tune BufferWrite calls for these nodes
    if self.options.use_dependency_analysis:
      for n in template.extends_nodes:
        for ext in template_extensions:
          path = os.path.join(
            *[ident_node.name
              for ident_node in n.source_module_name_list]) + ext
          template_function_names = get_template_functions(path)
          template.template_methods.update(template_function_names)
    
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

  def analyzeDictLiteralNode(self, dict_literal_node):
    for key_node, value_node in dict_literal_node.child_nodes:
      self.visit_ast(key_node, dict_literal_node)
      self.visit_ast(value_node, dict_literal_node)

  def analyzeCallFunctionNode(self, function_call):
    self.visit_ast(function_call.expression, function_call)
    self.visit_ast(function_call.arg_list, function_call)

  def analyzeBufferWrite(self, buffer_write):
    self.visit_ast(buffer_write.expression, buffer_write)
    # template functions output text - don't format them as strings
    if (isinstance(buffer_write.expression, BinOpNode) and
        buffer_write.expression.operator == '%' and
        isinstance(buffer_write.expression.right, CallFunctionNode) and
        isinstance(buffer_write.expression.right.expression,
                   TemplateMethodIdentifierNode)):
      buffer_write.replace(
        buffer_write.expression, buffer_write.expression.right)

  def analyzeEchoNode(self, node):
    for n in (node.test_expression, node.true_expression, node.false_expression):
      if n:
        self.visit_ast(n, node)


  def analyzeFilterNode(self, filter_node):
    self.visit_ast(filter_node.expression, filter_node)

    if (isinstance(filter_node.expression, CallFunctionNode) and
        isinstance(filter_node.expression.expression, TemplateMethodIdentifierNode)):
      filter_node.parent.replace(filter_node, filter_node.expression)
      return

    if self.options.cache_filtered_placeholders:
      # NOTE: you *must* analyze the node before putting it in a dict
      # otherwise the definition of hash and equivalence will change and the
      # node will not be found due to the sketchy custom hash function
      scope = self.get_parent_scope(filter_node)
      alias = scope.aliased_expression_map.get(filter_node)

      if not alias:
        alias_name = '_fph%08X' % unsigned_hash(filter_node.expression)
        if alias_name in scope.alias_name_set:
          print "duplicate alias_name", alias_name
          print "scope", scope
          print "scope.alias_name_set", scope.alias_name_set
          print "scope.aliased_expression_map", scope.aliased_expression_map
          return

        alias = IdentifierNode(alias_name)
        scope.alias_name_set.add(alias_name)
        scope.aliased_expression_map[filter_node] = alias
        assign_alias = AssignNode(alias, filter_node)

        insert_block, insert_marker = self.get_insert_block_and_point(
          filter_node)
        insert_block.insert_before(insert_marker, assign_alias)

      filter_node.parent.replace(filter_node, alias)
        

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
      elif placeholder.name in self.ast_root.template_methods:
        placeholder.parent.replace(
          placeholder, TemplateMethodIdentifierNode(
          placeholder.name))
      elif local_var in self.ast_root.global_identifiers:
        placeholder.parent.replace(placeholder, local_var)
      elif cached_placeholder in local_identifiers:
        placeholder.parent.replace(placeholder, cached_placeholder)
      elif local_var.name in builtin_names:
        placeholder.parent.replace(placeholder,
                                   IdentifierNode(local_var.name))
      elif self.options.cache_resolved_placeholders:
        scope = self.get_parent_scope(placeholder)
        scope.alias_name_set.add(cached_placeholder.name)
        scope.aliased_expression_map[placeholder] = cached_placeholder

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
        cached_placeholder.parent = assign_rph
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
      common_alias_name_set = if_node.scope.alias_name_set.intersection(
        if_node.else_.scope.alias_name_set)
      common_keys = (
        set(if_node.scope.aliased_expression_map.iterkeys()) &
        set(if_node.else_.scope.aliased_expression_map.iterkeys()))
      common_aliased_expression_map = {}
      for key in common_keys:
        common_aliased_expression_map[key] = if_node.scope.aliased_expression_map[key]

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
      

  def analyzeBinOpNode(self, n):
    # if you are trying to use short-circuit behavior, these two optimizations
    # can sabotage correct execution since the rhs may be hoisted above the
    # IfNode and cause it to get executed prior to passing the lhs check.
    if n.operator == 'and':
      cache_placeholders = self.options.cache_resolved_placeholders
      cache_udn_expressions = self.options.cache_resolved_udn_expressions
      self.options.cache_resolved_placeholders = False
      self.options.cache_resolved_udn_expressions = False
      
    self.visit_ast(n.left, n)
    self.visit_ast(n.right, n)

    if n.operator == 'and':
      self.options.cache_resolved_placeholders = cache_placeholders
      self.options.cache_resolved_udn_expressions = cache_udn_expressions

  analyzeBinOpExpressionNode = analyzeBinOpNode

  def analyzeUnaryOpNode(self, op_node):
    self.visit_ast(op_node.expression, op_node)

  def get_local_identifiers(self, node):
    local_identifiers = []
    
    # search the parent scopes
    # fixme: should this be recursive?
    node = node.parent
    while node is not None:
      if isinstance(node, ForNode):
        local_identifiers.extend(node.loop_variant_set)
        local_identifiers.extend(node.scope.local_identifiers)
      elif isinstance(node, IfNode):
        local_identifiers.extend(node.scope.local_identifiers)
      elif isinstance(node, ElseNode):
        # in this case, we don't want to go to the parent node, which is the
        # IfNode - we want to go to the parent 'scope'
        local_identifiers.extend(node.scope.local_identifiers)
        node = node.parent.parent
        continue
      elif isinstance(node, FunctionNode):
        local_identifiers.extend(node.scope.local_identifiers)
        break
      node = node.parent
    return frozenset(local_identifiers)
  
  def analyzeGetUDNNode(self, node):
    if not self.options.prefer_whole_udn_expressions:
      self.visit_ast(node.expression, node)
    
    if self.options.cache_resolved_udn_expressions:
      cached_udn = IdentifierNode('_rudn_%s' % unsigned_hash(node))
      local_identifiers = self.get_local_identifiers(node)
      if cached_udn in local_identifiers:
        node.parent.replace(node, cached_udn)
      else:
        insert_block, insert_marker = self.get_insert_block_and_point(
          node)

        # if there is a reassignment in the parent block, don't cache this
        # incase it needs to be re-resolved.
        # #set $text = $text.replace('\r\n', '\n')
        # #set $text = $text.replace('\t', '  ')
        # in this example, if you cache the udn expression text.replace,
        # you have a problem - you won't ever use the new string create by
        # the first call to replace
        for child_node in insert_block.child_nodes:
          if (isinstance(child_node, AssignNode) and
              child_node.left == node.expression):
            return

        scope = self.get_parent_scope(node)
        scope.alias_name_set.add(cached_udn.name)
        scope.aliased_expression_map[node] = cached_udn


        # note: this is sketchy enough that it requires some explanation
        # basically, you need to visit the node for the parent function to
        # get the memo that this value is aliased. unfortunately, the naive
        # case of just calling visit_ast blows up since it tries to double
        # analyze a certain set of nodes. you only really need to analyze
        # that the assignment took place, then you can safely alias the
        # actual function call. definitely sketchy, but it does seem to work
        assign_rph = AssignNode(cached_udn, None)
        cached_udn.parent = assign_rph
        insert_block.insert_before(
          insert_marker, assign_rph)
        self.visit_ast(assign_rph, insert_block)
        assign_rph.right = node
        node.parent.replace(node, cached_udn)
    elif self.options.prefer_whole_udn_expressions:
      self.visit_ast(node.expression, node)
      
      

  def analyzeSliceNode(self, pnode):
    self.visit_ast(pnode.expression, pnode)
    self.visit_ast(pnode.slice_expression, pnode)



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

  def hoist(self, parent_node, parent_block, insertion_point, alias_node,
            assign_alias_node):

    # prune the implementation in the nested block
    # print "prune", alias_node
    # print "parent_block aliases", parent_block.scope.aliased_expression_map
    parent_node.remove(assign_alias_node)
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
      if assign_alias_node in parent_block.child_nodes:
        current_pos = parent_block.child_nodes.index(assign_alias_node)
        # an else node's parent is the IfNode, which is the relevant
        # node when searching for the insertion point
        needed_pos = parent_block.child_nodes.index(insertion_point)
        if needed_pos < current_pos:
          parent_block.child_nodes.remove(assign_alias_node)
          if isinstance(parent_node, ElseNode):
            parent_block.insert_before(parent_node.parent, assign_alias_node)
          else:
            parent_block.insert_before(parent_node, assign_alias_node)
          # print "insert_before", alias_node
      else:
        # still need to insert the alias
        parent_block.insert_before(insertion_point, assign_alias_node)
      parent_block.scope.hoisted_aliases.append(alias_node)

      # NOTE: once we hoist an expression, we need to make sure that we no
      # longer use this for dependencies in the current scope
      del parent_node.scope.aliased_expression_map[alias_node]
      parent_node.scope.alias_name_set.remove(assign_alias_node.left.name)
      # FIXME: this is probably an indication of a bug or unnecessary
      # difference between the caching of placeholders and filter expressions
      if not isinstance(alias_node, FilterNode):
        parent_node.scope.local_identifiers.remove(assign_alias_node.left)


template_function_re = re.compile('^[^#]*#(def|block)\s+(\w+)')
extends_re = re.compile('^#extends\s+([\.\w]+)')
template_extensions = ('.spt', '.tmpl')
# scan an spt file for template functions it will output
def get_template_functions(path):
  template_function_names = set()
  if not os.path.exists(path):
    logging.debug('no such template for dependecy check: %s', path)
  else:
    f = open(path)
    for line in f:
      match = template_function_re.match(line)
      if match:
        template_function_names.add(match.group(2))
        continue
      match = extends_re.match(line)
      if match:
        extend_name = match.group(1)
        extend_path = extend_name.replace('.', '/')
        print 
        for ext in template_extensions:
          template_path = extend_path + ext
          template_function_names.update(
            get_template_functions(template_path))
        
  return template_function_names
