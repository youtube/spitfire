import copy
import os.path

from spitfire.compiler.ast import *
from spitfire.util import normalize_whitespace

def tree_walker(node):
  yield node
  for n in node.child_nodes:
    for ng in tree_walker(n):
      yield ng
  
class SemanticAnalyzerError(Exception):
  pass

class MacroError(SemanticAnalyzerError):
  pass

class MacroParseError(MacroError):
  pass

class AnalyzerOptions(object):

  def __init__(self, **kargs):
    self.debug = False
    
    self.ignore_optional_whitespace = False

    # adjacent text nodes become one single node
    self.collapse_adjacent_text = False

    # generate templates with unicode() instead of str()
    self.generate_unicode = True
    
    # runs of whitespace characters are replace with one space
    self.normalize_whitespace = False
    
    # expensive dotted notations are aliased to a local variable for faster
    # lookups: write = self.buffer.write
    self.alias_invariants = False

    # when a variable defined in a block later is accessed, just use the raw
    # identifier, don't incure the cost of a resolve_placeholder call since you
    # know that this local variable will always resolve first
    self.directly_access_defined_variables = False

    # examine the 'extends' directive to see what other methods will be
    # defined on this template - that allows use to make fast calls to template
    # methods outside of the immediate file.
    self.use_dependency_analysis = False

    # if directly_access_defined_variables is working 100% correctly, you can
    # compleletely ignore the local scope, as those placeholders will have been
    # resolved at compile time. there are some complex cases where there are
    # some problems, so it is disabled for now
    self.omit_local_scope_search = False

    # once a placeholder is resolved in a given scope, cache it in a local
    # reference for faster subsequent retrieval
    self.cache_resolved_placeholders = False
    self.cache_resolved_udn_expressions = False
    # when this is enabled, $a.b.c will cache only the result of the entire
    # expression. otherwise, each subexpression will be cached separately
    self.prefer_whole_udn_expressions = False
    
    # when adding an alias, detect if the alias is loop invariant and hoist
    # right there on the spot.  this has probably been superceded by
    # hoist_loop_invariant_aliases, but does have the advantage of not needing
    # another pass over the tree
    self.inline_hoist_loop_invariant_aliases = False

    # if an alias has been generated in a conditional scope and it is also
    # defined in the parent scope, hoist it above the conditional. this
    # requires a two-pass optimization on functions, which adds time and
    # complexity
    self.hoist_conditional_aliases = False
    self.hoist_loop_invariant_aliases = False

    # filtering is expensive, especially given the number of function calls
    self.cache_filtered_placeholders = False

    # generate functions compatible with Cheetah calling conventions
    self.cheetah_compatibility = False
    # use Cheetah NameMapper to resolve placeholders and UDN
    self.cheetah_cheats = False
    

    self.enable_psyco = False
    self.__dict__.update(kargs)

  def update(self, **kargs):
    self.__dict__.update(kargs)

  @classmethod
  def get_help(cls):
    return ', '.join(['[no-]' + name.replace('_', '-')
                    for name, value in vars(cls()).iteritems()
                    if not name.startswith('__') and type(value) == bool])
  
default_options = AnalyzerOptions()
o1_options = copy.copy(default_options)
o1_options.collapse_adjacent_text = True

o2_options = copy.copy(o1_options)
o2_options.alias_invariants = True
o2_options.directly_access_defined_variables = True
o2_options.cache_resolved_placeholders = True
o2_options.cache_resolved_udn_expressions = True
o2_options.inline_hoist_loop_invariant_aliases = True
o2_options.use_dependency_analysis = True

o3_options = copy.copy(o2_options)
o3_options.inline_hoist_loop_invariant_aliases = False
o3_options.hoist_conditional_aliases = True
o3_options.hoist_loop_invariant_aliases = True
o3_options.cache_filtered_placeholders = True

o4_options = copy.copy(o3_options)
o4_options.enable_psyco = True

optimizer_map = {
  0: default_options,
  1: o1_options,
  2: o2_options,
  3: o3_options,
  4: o4_options,
  }


i18n_function_name = 'i18n'

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
  def __init__(self, classname, parse_root, options, compiler):
    self.classname = classname
    self.parse_root = parse_root
    self.options = options
    self.compiler = compiler
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

    return ast_node_list

  def default_analyze_node(self, pnode):
    # print "default_analyze_node", type(pnode)
    return [pnode]

  # some nodes just don't need analysis
  def skip_analyze_node(self, pnode):
    return [pnode]
  analyzeIdentifierNode = skip_analyze_node
  analyzeLiteralNode = skip_analyze_node

  def analyzeTemplateNode(self, pnode):
    self.template = pnode.copy(copy_children=False)
    self.template.classname = self.classname

    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      built_nodes = self.build_ast(pn)
      if built_nodes:
        self.template.main_function.extend(built_nodes)

    self.template.main_function.child_nodes = self.optimize_buffer_writes(
      self.template.main_function.child_nodes)

    return [self.template]

  def analyzeForNode(self, pnode):
    for_node = ForNode()

    for pn in pnode.target_list.child_nodes:
      for_node.target_list.extend(self.build_ast(pn))
    for pn in pnode.expression_list.child_nodes:
      for_node.expression_list.extend(self.build_ast(pn))
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      for_node.extend(self.build_ast(pn))

    for_node.child_nodes = self.optimize_buffer_writes(for_node.child_nodes)

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
      if_node.child_nodes = self.optimize_buffer_writes(if_node.child_nodes)
    for pn in self.optimize_parsed_nodes(pnode.else_.child_nodes):
      if_node.else_.extend(self.build_ast(pn))
      if_node.else_.child_nodes = self.optimize_buffer_writes(
        if_node.else_.child_nodes)
    return [if_node]

  def analyzeFragmentNode(self, node):
    new_nodes = []
    for n in node.child_nodes:
      new_nodes.extend(self.build_ast(n))
    return new_nodes

  def analyzeArgListNode(self, pnode):
    list_node = ArgListNode()
    for n in pnode:
      list_node.extend(self.build_ast(n))
    return [list_node]

  def analyzeTupleLiteralNode(self, pnode):
    tuple_node = TupleLiteralNode()
    for n in pnode.child_nodes:
      tuple_node.extend(self.build_ast(n))
    return [tuple_node]

  def analyzeParameterNode(self, pnode):
    param = pnode
    param.default = self.build_ast(pnode.default)[0]
    return [param]

  def analyzeSliceNode(self, pnode):
    snode = pnode
    snode.expression = self.build_ast(pnode.expression)[0]
    snode.slice_expression = self.build_ast(pnode.slice_expression)[0]
    return [snode]

  # FIXME: should I move this to a directive?
  def analyzeImplementsNode(self, pnode):
    if pnode.name == 'library':
      self.template.library = True
    else:
      self.template.main_function.name = pnode.name
      self.template.implements = True
    return []

  def analyzeImportNode(self, pnode):
    node = ImportNode([self.build_ast(n)[0] for n in pnode.module_name_list])
    if node not in self.template.import_nodes:
      self.template.import_nodes.append(node)
    return []

  def analyzeExtendsNode(self, pnode):
    # an extends directive results in two fairly separate things happening
    # clone these nodes so we can modify the path struction without mangling
    # anything else
    import_node = ImportNode(pnode.module_name_list[:])
    extends_node = ExtendsNode(pnode.module_name_list[:])
    if (type(pnode) != AbsoluteExtendsNode and
        self.compiler.base_extends_package):
      # this means that extends are supposed to all happen relative to some
      # other package - this is handy for assuring all templates reference
      # within a tree, say for localization, where each local might have its
      # own package
      package_pieces = [IdentifierNode(module_name) for module_name in
                        self.compiler.base_extends_package.split('.')]
      import_node.module_name_list[0:0] = package_pieces
      extends_node.module_name_list[0:0] = package_pieces
      

    self.analyzeImportNode(import_node)

    # actually want to reference the class within the module name
    # assume we follow the convention of module name == class name
    extends_node.module_name_list.append(extends_node.module_name_list[-1])
    self.template.extends_nodes.append(extends_node)
    return []

  analyzeAbsoluteExtendsNode = analyzeExtendsNode

  def analyzeFromNode(self, pnode):
    if pnode not in self.template.from_nodes:
      self.template.from_nodes.append(pnode)
    return []

  def analyzeTextNode(self, pnode):
    if pnode.child_nodes:
      raise SemanticAnalyzerError("TextNode can't have children")
    text = pnode.value
    if self.options.normalize_whitespace:
      text = normalize_whitespace(text)
    return [BufferWrite(LiteralNode(text))]

  analyzeOptionalWhitespaceNode = analyzeTextNode
  analyzeWhitespaceNode = analyzeTextNode
  analyzeNewlineNode = analyzeTextNode

  # purely here for passthru and to remind me that it needs to be overridden
  def analyzeFunctionNode(self, pnode):
    return [pnode]

  def analyzeDefNode(self, pnode):
    #if not pnode.child_nodes:
    #  raise SemanticAnalyzerError("DefNode must have children")
    #if not isinstance(pnode.parent, TemplateNode):
    #  raise SemanticAnalyzerError("Nested #def or #block directives are not allowed")

    if pnode.name in self.template.template_methods:
      raise SemanticAnalyzerError('Redefining #def/#block %s' % pnode.name)
    
    self.template.template_methods.add(pnode.name)
    function = FunctionNode(pnode.name)
    if pnode.parameter_list:
      function.parameter_list = self.build_ast(pnode.parameter_list)[0]

    function.parameter_list.child_nodes.insert(0,
                                               ParameterNode(name='self'))
    
    for pn in self.optimize_parsed_nodes(pnode.child_nodes):
      function.extend(self.build_ast(pn))
    function = self.build_ast(function)[0]
    function.child_nodes = self.optimize_buffer_writes(function.child_nodes)
    self.template.append(function)
    return []

  def analyzeBlockNode(self, pnode):
    #if not pnode.child_nodes:
    #  raise SemanticAnalyzerError("BlockNode must have children")
    self.analyzeDefNode(pnode)
    function_node = CallFunctionNode()
    function_node.expression = self.build_ast(PlaceholderNode(pnode.name))[0]
    p = PlaceholderSubstitutionNode(function_node)
    call_block = self.build_ast(p)
    return call_block

  def handleMacro(self, pnode, macro_function):
    if isinstance(pnode, MacroNode):
      kargs_map = pnode.parameter_list.get_arg_map()
    elif isinstance(pnode, CallFunctionNode):
      kargs_map = pnode.arg_list.get_arg_map()
    else:
      raise SemanticAnalyzerError("unexpected node type '%s' for macro" %
                                  type(pnode))

    macro_output = macro_function(pnode, kargs_map, self.compiler)
    # fixme: bad place to import, difficult to put at the top due to
    # cyclic dependency
    import spitfire.compiler.util
    try:
      if isinstance(pnode, MacroNode):
        fragment_ast = spitfire.compiler.util.parse(
          macro_output, 'fragment_goal')
      elif isinstance(pnode, CallFunctionNode):
        fragment_ast = spitfire.compiler.util.parse(
          macro_output, 'rhs_expression')
    except Exception, e:
      raise MacroParseError(e)
    return self.build_ast(fragment_ast)

  def analyzeMacroNode(self, pnode):
    # fixme: better error handler
    macro_handler_name = 'macro_%s' % pnode.name
    try:
      macro_function = self.compiler.macro_registry[macro_handler_name]
    except KeyError:
      raise SemanticAnalyzerError("no handler registered for '%s'"
                                  % macro_handler_name)
    return self.handleMacro(pnode, macro_function)

  def analyzeAttributeNode(self, pnode):
    self.template.attr_nodes.append(pnode)
    return []

  analyzeFilterAttributeNode = analyzeAttributeNode

  # note: we do a copy-thru to force analysis of the child nodes
  # this function is drastically complicated by the logic for filtering
  # basically, if you are pulling data from the search_list and writing it
  # to the output buffer, you want to do some filtering in most cases - at
  # least when you are doing web stuff.
  # there are some cases where you want to disable this to prevent double
  # escaping or to increase performance by avoiding unnecessay work.
  #
  # $test_str_function($test_dict)
  #
  # self.resolve_placeholder('test_str_function', local_vars=locals(),
  #   global_vars=_globals)(self.resolve_placeholder('test_dict',
  #   local_vars=locals(), global_vars=_globals))
  #
  # if this section is referenced inside another template-defined function the
  # data returned should not be double escaped. you can do this by forcing all
  # template functions to annotate themselves, but you have to do more
  # cumbersome checks when you are calling arbitrary functions.
  #
  # it might be reasonable to put in another node type that indicates a block
  # of data needs to be filtered.
  def analyzePlaceholderSubstitutionNode(self, pnode):
    #print "analyzePlaceholderSubstitutionNode", pnode, pnode.parameter_list.get_arg_map()
    node_list = []
    ph_expression = self.build_ast(pnode.expression)[0]

    arg_map = pnode.parameter_list.get_arg_map()
    default_format_string = '%s'
    format_string = arg_map.get('format_string', default_format_string)

    skip_filter = False
    cache_forever = False
    registered_function = False
    function_has_only_literal_args = False
    never_cache = False
    if isinstance(ph_expression, CallFunctionNode):
      fname = ph_expression.expression.name
      registered_function = (fname in self.compiler.function_name_registry)
      if registered_function:
        function_has_only_literal_args = (
          ph_expression.arg_list and
          not [_arg for _arg in ph_expression.arg_list
               if not isinstance(_arg, LiteralNode)])
        if self.compiler.new_registry_format:
          decorators = self.compiler.function_name_registry[fname][-1]
          skip_filter = 'skip_filter' in decorators
          cache_forever = 'cache_forever' in decorators
          never_cache = 'never_cache' in decorators
        else:
          ph_function = self.compiler.function_name_registry[fname][-1]
          skip_filter = getattr(ph_function, 'skip_filter', False)
          cache_forever = getattr(ph_function, 'cache_forever', False)
          never_cache = getattr(ph_function, 'never_cache', False)

    if (self.compiler.enable_filters and
        format_string == default_format_string and
        not isinstance(ph_expression, LiteralNode)):
      arg_node_map = pnode.parameter_list.get_arg_node_map()
      if 'raw' not in arg_map:
        # if we need to filter, wrap up the node and wait for further analysis
        # later on
        if skip_filter:
          # explicitly set the filter to none here - this means we will cache
          # expensive pseudo-filtered nodes
          ph_expression = FilterNode(ph_expression, None)
        else:
          ph_expression = FilterNode(
            ph_expression, arg_node_map.get('filter', DefaultFilterFunction))

        # if this is a literal node, we still might want to filter it
        # but the output should always be the same - so do it once and cache
        # FIXME: could fold this and apply the function at compile-time
        if (not never_cache and
            (registered_function and function_has_only_literal_args) or
            cache_forever or 'cache' in arg_map):
          cache_expression = CacheNode(ph_expression)
          self.template.cached_identifiers.add(cache_expression)
          node_list.append(cache_expression)
          ph_expression = IdentifierNode(cache_expression.name)

    if isinstance(ph_expression, LiteralNode):
      node_list.append(BufferWrite(ph_expression))
    elif self.compiler.enable_filters and format_string == default_format_string:
      # we are already filtering, don't bother creating a new string
      node_list.append(BufferWrite(ph_expression))
    else:
      node_list.append(BufferWrite(BinOpNode('%', LiteralNode(format_string),
                                             ph_expression)))
    return node_list


  def analyzePlaceholderNode(self, pnode):
    return [pnode]

  analyzeEchoNode = analyzePlaceholderNode

  def analyzeBinOpNode(self, pnode):
    n = pnode
    n.left = self.build_ast(n.left)[0]
    n.right = self.build_ast(n.right)[0]
    return [n]

  analyzeBinOpExpressionNode = analyzeBinOpNode
  analyzeAssignNode = analyzeBinOpNode
  
  def analyzeUnaryOpNode(self, pnode):
    n = pnode
    n.expression = self.build_ast(n.expression)[0]
    return [n]

  def analyzeCommentNode(self, pnode):
    return []

  def analyzeCallFunctionNode(self, pnode):
    fn = pnode
    if isinstance(fn.expression, PlaceholderNode):
      macro_handler_name = 'macro_function_%s' % fn.expression.name
      macro_function = self.compiler.macro_registry.get(macro_handler_name)
      if macro_function:
        return self.handleMacro(fn, macro_function)
    fn.expression = self.build_ast(fn.expression)[0]
    fn.arg_list = self.build_ast(fn.arg_list)[0]
    return [fn]

  analyzeBufferWrite = analyzeCallFunctionNode

  def analyzeFilterNode(self, pnode):
    fn = pnode
    fn.expression = self.build_ast(fn.expression)[0]
    return [fn]

  # go over the parsed nodes and weed out the parts we don't need
  # it's easier to do this before we morph the AST to look more like python
  def optimize_parsed_nodes(self, node_list):
    optimized_nodes = []
    for n in node_list:
      # strip optional whitespace by removing the nodes
      if (self.options.ignore_optional_whitespace and
          isinstance(n, OptionalWhitespaceNode)):
        continue
      # collapse adjacent TextNodes so we are calling these buffer writes
      elif (self.options.collapse_adjacent_text and
            isinstance(n, TextNode) and
            len(optimized_nodes) and
            isinstance(optimized_nodes[-1], TextNode)):
        # recreate this object so it doesn't show up as whitespace
        temp_text = TextNode(optimized_nodes[-1].value)
        temp_text.parent = optimized_nodes[-1].parent
        temp_text.append_text_node(n)
        optimized_nodes[-1] = temp_text
      else:
        optimized_nodes.append(n)
    #print "optimized_nodes", node_list, optimized_nodes
    return optimized_nodes

  # go over the parsed nodes and weed out the parts we don't need
  # do this after analysis as well, in case a macro generates more BufferWrite
  def optimize_buffer_writes(self, node_list):
    optimized_nodes = NodeList()
    for n in node_list:
      if (self.options.collapse_adjacent_text and
          is_text_write(n) and
          len(optimized_nodes) and
          is_text_write(optimized_nodes[-1])):
        optimized_nodes[-1].append_text_node(n)
      else:
        optimized_nodes.append(n)
    return optimized_nodes

def is_text_write(node):
  return (isinstance(node, BufferWrite) and
          isinstance(node.expression, LiteralNode))
  
