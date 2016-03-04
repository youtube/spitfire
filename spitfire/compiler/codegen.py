# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import logging

import cStringIO as StringIO

from spitfire.compiler import ast


class CodegenError(Exception):
    pass


class CodeNode(object):

    def __init__(self, src_line=None, input_pos=None):
        self.src_line = src_line
        self.input_pos = input_pos
        self.child_nodes = []

    def append_line(self, line):
        self.append(CodeNode(line))

    def append(self, code_node):
        self.child_nodes.append(code_node)

    def insert(self, index, code_node):
        self.child_nodes.insert(index, code_node)

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
    def __init__(self, ast_root, compiler, options=None):
        self.ast_root = ast_root
        # Compiler - an instance of Compiler defined in util.
        self.compiler = compiler
        # This stack of FunctionNodes represents the functions we are
        # currently inside. When we enter a function node, we push that
        # onto the stack and when we leave that function, we pop it from
        # the stack.
        self.function_stack = []
        self.options = options
        self.output = StringIO.StringIO()
        self.template = None
        self.baked_mode = False

    def get_code(self):
        code_root = self.build_code(self.ast_root)[0]
        self.write_python(code_root, indent_level=-1)
        return self.output.getvalue().encode(self.ast_root.encoding)

    def generate_python(self, code_node):
        try:
            return code_node.src_line
        except AttributeError, e:
            self.compiler.error(CodegenError("can't write code_node: %s\n\t%s" %
                                             (code_node, e)))

    def write_python(self, code_node, indent_level):
        try:
            if code_node.src_line is not None:
                if code_node.src_line:
                    self.output.write(self.indent_str * indent_level)
                    self.output.write(code_node.src_line)
                    if (self.options.include_sourcemap and
                            code_node.input_pos and self.compiler.src_line_map):
                        self.output.write(
                            ' # L%s' %
                            self.compiler.src_line_map[code_node.input_pos])
                self.output.write('\n')
        except AttributeError:
            self.compiler.error(CodegenError("can't write code_node: %s" %
                                             code_node))

        for cn in code_node.child_nodes:
            self.write_python(cn, indent_level + 1)

    def build_code(self, ast_node):
        method_name = 'codegenAST%s' % ast_node.__class__.__name__
        method = getattr(self, method_name, self.codegenDefault)
        return method(ast_node)

    def codegenASTTemplateNode(self, node):
        self.template = node.copy(copy_children=False)

        module_code = CodeNode()
        module_code.append_line('#!/usr/bin/env python')
        module_code.append_line('# -*- coding: %s -*-' % node.encoding)
        if node.baked:
            module_code.append_line('# Baked Mode')
            self.baked_mode = True
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

        classname = node.classname

        module_code.append_line('import spitfire.runtime')
        module_code.append_line('import spitfire.runtime.template')

        if self.options and self.options.cheetah_cheats:
            module_code.append_line(
                'from Cheetah.NameMapper import valueFromSearchList '
                'as resolve_placeholder')
            module_code.append_line(
                'from Cheetah.NameMapper import valueForKey as resolve_udn')
        else:
            module_code.append_line(
                'from spitfire.runtime.udn import resolve_placeholder')
            module_code.append_line('from spitfire.runtime.udn '
                                    'import resolve_placeholder_with_locals')
            module_code.append_line(
                'from spitfire.runtime.udn import resolve_udn')

        module_code.append_line(
            'from spitfire.runtime.baked import SanitizedPlaceholder')
        module_code.append_line(
            'from spitfire.runtime.baked import runtime_mark_as_sanitized')
        module_code.append_line(
            'from spitfire.runtime.baked import mark_as_sanitized')
        module_code.append_line(
            'from spitfire.runtime.template import template_method')
        module_code.append_line('')

        if node.cached_identifiers:
            module_code.append_line('# cached identifiers')
            for cached_ph in node.cached_identifiers:
                module_code.append_line('%s = None' % cached_ph.name)
            module_code.append_line('')

        if not node.library:
            extends = []
            for n in node.extends_nodes:
                extends.append(self.generate_python(self.build_code(n)[0]))
            if not extends:
                extends = [self.options.base_template_full_import_path]
                if (self.options.base_template_full_import_path !=
                    (self.options.DEFAULT_BASE_TEMPLATE_FULL_IMPORT_PATH)):
                    # If we are not using the default base template class, we
                    # need to import the module for the custom template class.
                    # The module for the default base template class is already
                    # imported below and is required regardless of which base
                    # template is being used.
                    base_template_module_bits = (
                        self.options.base_template_full_import_path.split(
                            '.')[:-1])
                    # If the full import path is a.b.ClassName, we want to
                    # import the module a.b.
                    base_template_module = '.'.join(base_template_module_bits)
                    module_code.append_line('import %s' % base_template_module)

            extends_clause = ', '.join(extends)
            class_code = CodeNode('class %(classname)s(%(extends_clause)s):' %
                                  vars())

            module_code.append(class_code)
            for n in node.attr_nodes:
                class_code.extend(self.build_code(n))
                class_code.append_line('')
            def_parent_code = class_code
        else:
            # Library functions are written to the module directly.
            module_code.append_line('')
            def_parent_code = module_code

        for n in node.child_nodes:
            def_parent_code.extend(self.build_code(n))
            def_parent_code.append_line('')

        # if we aren't extending a template, build out the main function
        if not node.library and (not node.extends_nodes or node.implements):
            def_parent_code.extend(self.build_code(node.main_function))

        # NOTE(msolo): originally, i thought this would be helpful in case a bit
        # of human error - however, a more robust check is necessary here to
        # make the warning less spurious
        # else:
        #   from spitfire.compiler.visitor import flatten_tree
        #   logging.warning(throwing away defined main function because "
        #                   "it is not a base class %s %s",
        #                   self.ast_root.source_path)
        #   logging.warning("%s", flatten_tree(node.main_function))

        module_code.append_line(run_tmpl % vars(node))

        return [module_code]

    def codegenASTExtendsNode(self, node):
        return [CodeNode('.'.join([
            self.generate_python(self.build_code(n)[
                0]) for n in node.module_name_list
        ]))]

    def codegenASTImportNode(self, node):
        return [CodeNode('import %s' % '.'.join([
            self.generate_python(self.build_code(n)[
                0]) for n in node.module_name_list
        ]))]

    def codegenASTFromNode(self, node):
        from_clause = '.'.join([
            self.generate_python(self.build_code(n)[
                0]) for n in node.module_name_list
        ])
        import_clause = self.generate_python(self.build_code(node.identifier)[
            0])

        if node.alias:
            alias_clause = self.generate_python(self.build_code(node.alias)[0])
            return [CodeNode('from %(from_clause)s '
                             'import %(import_clause)s '
                             'as %(alias_clause)s' % vars())]
        else:
            return [CodeNode('from %(from_clause)s '
                             'import %(import_clause)s' % vars())]

    def codegenASTPlaceholderSubstitutionNode(self, node):
        placeholder = self.generate_python(self.build_code(node.expression)[0])
        return [CodeNode(ASTPlaceholderSubstitutionNode_tmpl[0] % vars(),
                         input_pos=node.pos)]

    def codegenASTDoNode(self, node):
        return [CodeNode(
            self.generate_python(self.build_code(node.expression)[0]),
            input_pos=node.pos)]

    def codegenASTCallFunctionNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        if expression == '_self_filter_function':
            self.function_stack[-1].uses_filter_function = True
        if expression == '_self_private_filter_function':
            self.function_stack[-1].uses_private_filter_function = True
        if node.arg_list:
            arg_list = self.generate_python(self.build_code(node.arg_list)[0])
        else:
            arg_list = ''
        call = ASTCallFunctionNode_tmpl[0] % vars()
        if self.baked_mode:
            sanitization_state = node.sanitization_state
            # For SANITIZED_STRING we could use SanitizedPlaceholder(), but the
            # mark_as_sanitized() function is faster so we use that instead.
            if (sanitization_state == ast.SanitizedState.SANITIZED_STRING or
                    sanitization_state == ast.SanitizedState.SANITIZED):
                return [CodeNode('mark_as_sanitized(%s)' % call,
                                 input_pos=node.pos)]
            elif (sanitization_state == ast.SanitizedState.UNSANITIZED or
                  sanitization_state == ast.SanitizedState.NOT_OUTPUTTED or
                  sanitization_state ==
                  ast.SanitizedState.OUTPUTTED_IMMEDIATELY):
                return [CodeNode(call, input_pos=node.pos)]
            elif sanitization_state == ast.SanitizedState.UNKNOWN:
                return [CodeNode(
                    'runtime_mark_as_sanitized(%(call)s, %(expression)s)' %
                    vars(),
                    input_pos=node.pos)]
        return [CodeNode(call, input_pos=node.pos)]

    def codegenASTForNode(self, node):
        target_list = self.generate_python(self.build_code(node.target_list)[0])
        expression_list = self.generate_python(self.build_code(
            node.expression_list)[0])
        code_node = CodeNode(ASTForNode_tmpl[0] % vars(), input_pos=node.pos)
        for n in node.child_nodes:
            code_node.extend(self.build_code(n))
        return [code_node]

    def codegenASTIfNode(self, node):
        test_expression = self.generate_python(self.build_code(
            node.test_expression)[0])
        if_code_node = CodeNode("if %(test_expression)s:" % vars(),
                                input_pos=node.pos)
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
            return [CodeNode('(%s)' % ', '.join([self.generate_python(
                self.build_code(n)[0]) for n in node.child_nodes]))]

    codegenASTExpressionListNode = codegenASTTargetListNode

    def codegenASTLiteralNode(self, node):
        if (self.options and not self.options.generate_unicode and
                isinstance(node.value, basestring)):
            # If the node is the empty string, we should mark it as sanitized by
            # default. Eventually, all string literals should be marked as
            # sanitized.
            if self.baked_mode and node.value == '':
                return [CodeNode("mark_as_sanitized('')", input_pos=node.pos)]

            return [CodeNode(
                repr(node.value.encode(self.ast_root.encoding)),
                input_pos=node.pos)]
        else:
            # generate unicode by default
            return [CodeNode('%(value)r' % vars(node), input_pos=node.pos)]

    def codegenASTListLiteralNode(self, node):
        return [CodeNode('[%s]' % ', '.join([
            self.generate_python(self.build_code(n)[
                0]) for n in node.child_nodes
        ]),
                         input_pos=node.pos)]

    def codegenASTTupleLiteralNode(self, node):
        return [CodeNode('(%s)' % ', '.join([
            self.generate_python(self.build_code(n)[
                0]) for n in node.child_nodes
        ]),
                         input_pos=node.pos)]

    def codegenASTDictLiteralNode(self, node):
        return [
            CodeNode('{%s}' % ', '.join([
                '%s: %s' % (self.generate_python(self.build_code(kn)[
                    0]), self.generate_python(self.build_code(vn)[0])
                           ) for kn, vn in node.child_nodes
            ]))
        ]

    def codegenASTParameterNode(self, node):
        if node.default:
            return [CodeNode('%s=%s' % (
                node.name,
                self.generate_python(self.build_code(node.default)[0])))]
        else:
            return [CodeNode('%s' % node.name)]

    def codegenASTAttributeNode(self, node):
        return [CodeNode('%s = %s' % (
            node.name, self.generate_python(self.build_code(node.default)[0])),
                         input_pos=node.pos)]

    def codegenASTFilterAttributeNode(self, node):
        return [CodeNode('%s = staticmethod(%s)' % (
            node.name, self.generate_python(self.build_code(node.default)[0])))]

    def codegenASTParameterListNode(self, node):
        if len(node.child_nodes) == 1:
            return self.build_code(node.child_nodes[0])
        else:
            return [CodeNode('%s' % ', '.join([self.generate_python(
                self.build_code(n)[0]) for n in node.child_nodes]))]

    codegenASTArgListNode = codegenASTParameterListNode

    def codegenASTGetUDNNode(self, node):
        #print ' '.join("codegenASTGetUDNNode", id(node), "name", node.name,
        #               "expr", node.expression)
        expression = self.generate_python(self.build_code(node.expression)[0])
        name = node.name
        if (self.options and self.options.default_to_strict_resolution and
                self.template and not self.template.use_loose_resolution):
            return [CodeNode("%(expression)s.%(name)s" % vars())]
        if self.options and self.options.raise_udn_exceptions:
            return [CodeNode(
                "resolve_udn(%(expression)s, '%(name)s', raise_exception=True)"
                % vars(),
                input_pos=node.pos)]
        else:
            return [CodeNode("resolve_udn(%(expression)s, '%(name)s')" % vars(),
                             input_pos=node.pos)]

    def codegenASTPlaceholderNode(self, node):
        name = node.name
        if name in ('has_var', 'get_var'):
            return [CodeNode("self.%(name)s" % vars())]
        elif self.options and self.options.cheetah_cheats:
            return [CodeNode("resolve_placeholder([locals()] + "
                             "_self_search_list, '%(name)s')" % vars(),
                             input_pos=node.pos)]
        elif self.options and self.options.omit_local_scope_search:
            self.function_stack[-1].uses_globals = True
            return [CodeNode("resolve_placeholder('%(name)s', self, _globals)" %
                             vars(),
                             input_pos=node.pos)]
        else:
            self.function_stack[-1].uses_globals = True
            return [CodeNode("resolve_placeholder_with_locals('%(name)s', "
                             "self, locals(), _globals)" % vars(),
                             input_pos=node.pos)]

    def codegenASTReturnNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        return [CodeNode("return %(expression)s" % vars(), input_pos=node.pos)]

    def codegenASTOptionalWhitespaceNode(self, node):
        #if self.ignore_optional_whitespace:
        #  return []
        return [CodeNode(ASTOptionalWhitespaceNode_tmpl[0] % vars(node),
                         input_pos=node.pos)]

    def codegenASTSliceNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        slice_expression = self.generate_python(self.build_code(
            node.slice_expression)[0])
        return [CodeNode("%(expression)s[%(slice_expression)s]" % vars())]

    def codegenASTBinOpExpressionNode(self, node):
        left = self.generate_python(self.build_code(node.left)[0])
        right = self.generate_python(self.build_code(node.right)[0])
        operator = node.operator
        return [CodeNode('(%(left)s %(operator)s %(right)s)' % vars(),
                         input_pos=node.pos)]

    def codegenASTBinOpNode(self, node):
        left = self.generate_python(self.build_code(node.left)[0])
        right = self.generate_python(self.build_code(node.right)[0])
        operator = node.operator
        return [CodeNode('%(left)s %(operator)s %(right)s' % vars(),
                         input_pos=node.pos)]

    codegenASTAssignNode = codegenASTBinOpNode

    def codegenASTUnaryOpNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        operator = node.operator
        return [CodeNode('(%(operator)s %(expression)s)' % vars(),
                         input_pos=node.pos)]

    def codegenASTGetAttrNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        name = node.name
        return [CodeNode("%(expression)s.%(name)s" % vars(),
                         input_pos=node.pos)]

    def codegenASTFunctionNode(self, node):
        name = node.name
        node.uses_globals = False
        node.uses_filter_function = False
        node.uses_private_filter_function = False
        node.uses_buffer_write = False
        node.uses_buffer_extend = False
        self.function_stack.append(node)
        if node.parameter_list:
            parameter_list = self.generate_python(self.build_code(
                node.parameter_list)[0])
        else:
            parameter_list = ''

        decorator_node = CodeNode('@template_method')
        # NOTE: for Cheetah compatibility, we have to handle the case where
        # Cheetah tries to pass a 'transaction' object through. hopefully this
        # doesn't have some other baggage coming with it.
        if self.options and self.options.cheetah_compatibility:
            if parameter_list:
                code_node = CodeNode(
                    'def %(name)s(%(parameter_list)s, **kargs):' % vars(),
                    input_pos=node.pos)
            else:
                code_node = CodeNode('def %(name)s(**kargs):' % vars(),
                                     input_pos=node.pos)
        else:
            code_node = CodeNode('def %(name)s(%(parameter_list)s):' % vars(),
                                 input_pos=node.pos)

        needs_globals_added = True
        child_nodes = node.child_nodes

        if self.options and self.options.cheetah_compatibility:
            if_cheetah = CodeNode("if 'trans' in kargs:")
            code_node.append(if_cheetah)
            if_cheetah.append(CodeNode("_buffer = kargs['trans'].response()"))
            else_spitfire = CodeNode('else:')
            else_spitfire.append(CodeNode('_buffer = self.new_buffer()'))
            code_node.append(else_spitfire)
        else:
            # If the first node is an if statement with no else AND there's no
            # other statements, generate the if code first.  That way, we can
            # avoid doing extra work when the condition is false.  ie, avoid the
            # overhead of creating a new list setting up useless local variables
            # and joining all to get an empty string. Disable this in baked mode
            # until I figure out how to handle this. TODO: Do not perform
            # sanitization inside of a test_expression. Then we can remove this
            # baked_mode check.
            if child_nodes and len(child_nodes) == 1 and not self.baked_mode:
                if_node = child_nodes[0]
                if isinstance(if_node,
                              ast.IfNode) and not if_node.else_.child_nodes:
                    child_nodes = if_node.child_nodes
                    # Insert code that does:
                    #   if not ($test_expression):
                    #     return ''
                    new_if_condition = ast.IfNode(ast.UnaryOpNode(
                        'not', if_node.test_expression))
                    new_if_condition.append(ast.ReturnNode(ast.LiteralNode('')))
                    new_code = self.build_code(new_if_condition)
                    if node.uses_globals:
                        needs_globals_added = False
                        code_node.append(CodeNode('_globals = globals()'))
                    code_node.extend(new_code)

            code_node.append(CodeNode('_buffer = self.new_buffer()'))

        # Save the point where _globals and self_filter_funtion will go if used.
        # We don't append these here because we have to determine if these two
        # functions are used in the scope of the current ast.FunctionNode.
        insertion_point = len(code_node.child_nodes)

        if self.options and self.options.cheetah_cheats:
            node.uses_globals = True
            if_cheetah = CodeNode('if self.search_list:')
            if_cheetah.append(CodeNode(
                '_self_search_list = self.search_list + [_globals]'))
            else_cheetah = CodeNode('else:')
            else_cheetah.append(CodeNode('_self_search_list = [_globals]'))
            code_node.append(if_cheetah)
            code_node.append(else_cheetah)

        for n in child_nodes:
            code_child_nodes = self.build_code(n)
            code_node.extend(code_child_nodes)

        if node.uses_globals and needs_globals_added:
            code_node.insert(insertion_point, CodeNode('_globals = globals()'))
            insertion_point += 1
        if node.uses_filter_function:
            code_node.insert(
                insertion_point,
                CodeNode('_self_filter_function = self.filter_function'))
            insertion_point += 1
        if node.uses_private_filter_function:
            code_node.insert(insertion_point, CodeNode(
                '_self_private_filter_function = self._filter_function'))
            insertion_point += 1
        if node.uses_buffer_write:
            code_node.insert(insertion_point,
                             CodeNode('_buffer_write = _buffer.write'))
            insertion_point += 1
        if node.uses_buffer_extend:
            code_node.insert(insertion_point,
                             CodeNode('_buffer_extend = _buffer.extend'))
        if self.options.cheetah_compatibility:
            if_cheetah = CodeNode("if 'trans' not in kargs:")
            if_cheetah.append(CodeNode('return _buffer.getvalue()'))
            code_node.append(if_cheetah)
        else:
            code_node.append(CodeNode('return _buffer.getvalue()'))
        self.function_stack.pop()
        return [decorator_node, code_node]

    # fixme: don't know if i still need this - a 'template function'
    # has an implicit return of the buffer built in - might be simpler
    # to code that rather than adding a return node during the analyze
    #def codegenASTReturnNode(self, node):
    #  code_node = self.codegenDefault(node)

    def codegenASTBufferWrite(self, node):
        self.function_stack[-1].uses_buffer_write = True
        expression = self.generate_python(self.build_code(node.expression)[0])
        code_node = CodeNode('_buffer_write(%(expression)s)' % vars(),
                             input_pos=node.pos)
        return [code_node]

    def codegenASTBufferExtend(self, node):
        self.function_stack[-1].uses_buffer_extend = True
        expression = self.generate_python(self.build_code(node.expression)[0])
        code_node = CodeNode('_buffer_extend(%(expression)s)' % vars(),
                             input_pos=node.pos)
        return [code_node]

    def codegenASTEchoNode(self, node):
        self.function_stack[-1].uses_buffer_write = True
        node_list = []

        true_expression = self.generate_python(self.build_code(
            node.true_expression)[0])
        true_code = CodeNode('_buffer_write(%(true_expression)s)' % vars())
        if node.test_expression:
            test_expression = self.generate_python(self.build_code(
                node.test_expression)[0])
            if_code = CodeNode('if %(test_expression)s:' % vars())
            if_code.append(true_code)
            node_list.append(if_code)
        else:
            node_list.append(true_code)

        if node.false_expression:
            false_expression = self.generate_python(self.build_code(
                node.false_expression)[0])
            else_code = CodeNode('else:' % vars())
            else_code.append(CodeNode('_buffer_write(%(false_expression)s)' %
                                      vars()))
            node_list.append(else_code)
        return node_list

    def codegenASTCacheNode(self, node):
        self.function_stack[-1].uses_globals = True
        cached_name = node.name
        expression = self.generate_python(self.build_code(node.expression)[0])
        # use dictionary syntax to get around coalescing 'global' statements
        #globalize_var = CodeNode('global %(cached_name)s' % vars())
        if_code = CodeNode("if %(cached_name)s is None:" % vars(),
                           input_pos=node.pos)
        if_code.append(
            CodeNode("_globals['%(cached_name)s'] = %(expression)s" % vars(),
                     input_pos=node.pos))
        return [if_code]

    def codegenASTFilterNode(self, node):
        expression = self.generate_python(self.build_code(node.expression)[0])
        if node.filter_function_node == ast.DefaultFilterFunction:
            # In baked mode, we must always call into _self_filter_function.
            # This is because this is the function that will contain the logic
            # for deciding whether or not to filter a SanitizedPlaceholder.
            if isinstance(node.expression,
                          ast.CallFunctionNode) or self.baked_mode:
                self.function_stack[-1].uses_filter_function = True
                filter_expression = '_self_filter_function'
            else:
                # Since there is no second argument to filter_function, there
                # will be a call to _filter_function. This optimization skips
                # the check and calls directly to _filter_function.
                self.function_stack[-1].uses_private_filter_function = True
                filter_expression = '_self_private_filter_function'
        elif node.filter_function_node:
            filter_expression = self.generate_python(self.build_code(
                node.filter_function_node)[0])
        else:
            filter_expression = None

        if isinstance(node.expression, ast.CallFunctionNode):
            # need the placeholder function expression to make sure that we
            # don't double escape the output of template functions
            # fixme: this is suboptimal if this expression is expensive -
            # should the optimizer fix this, or should we generate speedy code?
            placeholder_function_expression = self.generate_python(
                self.build_code(node.expression.expression)[0])
            if node.filter_function_node == ast.DefaultFilterFunction:
                code_node = CodeNode('%(filter_expression)s(%(expression)s, '
                                     '%(placeholder_function_expression)s)' %
                                     vars(),
                                     input_pos=node.pos)
            elif node.filter_function_node:
                code_node = CodeNode(
                    '%(filter_expression)s(self, '
                    '%(expression)s, %(placeholder_function_expression)s)' %
                    vars(),
                    input_pos=node.pos)
            else:
                code_node = CodeNode('%(expression)s' % vars(),
                                     input_pos=node.pos)
        else:
            if node.filter_function_node == ast.DefaultFilterFunction:
                code_node = CodeNode('%(filter_expression)s(%(expression)s)' %
                                     vars(),
                                     input_pos=node.pos)
            elif node.filter_function_node:
                code_node = CodeNode('%(filter_expression)s(%(expression)s)' %
                                     vars(),
                                     input_pos=node.pos)
            else:
                code_node = CodeNode('%(expression)s' % vars(),
                                     input_pos=node.pos)
        return [code_node]

    def codegenDefault(self, node):
        v = globals()
        try:
            return [CodeNode(line % vars(node))
                    for line in v['AST%s_tmpl' % node.__class__.__name__]]
        except KeyError, e:
            self.compiler.error(CodegenError("no codegen for %s %s" % (type(
                node), vars(node))))

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
