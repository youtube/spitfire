# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import StringIO


class TreeWalkError(Exception):
    pass


class VisitNode(object):

    def __init__(self, node_repr=None, child_nodes=None):
        self.node_repr = node_repr
        if child_nodes is None:
            self.child_nodes = []
        else:
            self.child_nodes = child_nodes

    def append_line(self, line):
        self.append(VisitNode(line))

    def append(self, visit_node):
        self.child_nodes.append(visit_node)

    def extend(self, visit_nodes):
        try:
            self.child_nodes.extend(visit_nodes)
        except TypeError:
            raise TreeWalkError("can't add %s" % visit_nodes)

    def __repr__(self):
        return '%s:%s' % (self.__class__.__name__, self.node_repr)


def flatten_tree(root):
    return TreeVisitor(root).get_text()


def print_tree(root, output=None):
    if output:
        print >> output, flatten_tree(root)
    else:
        print flatten_tree(root)


# perform an in-order traversal of the AST and call the generate methods
# in this case, we are generating python source code that should be somewhat
# human-readable
class TreeVisitor(object):
    indent_str = '  '
    indent_level = 0

    def __init__(self, ast_root):
        self.ast_root = ast_root
        self.output = StringIO.StringIO()

    def get_text(self):
        root = self.build_text(self.ast_root)[0]
        self.write_visit(root)
        text = self.output.getvalue()
        try:
            text = text.encode(self.ast_root.encoding)
        except AttributeError, e:
            pass
        return text

    def generate_text(self, visit_node):
        try:
            return visit_node.node_repr
        except AttributeError, e:
            raise TreeWalkError("can't write visit_node: %s\n\t%s" %
                                (visit_node, e))

    def write_visit(self, visit_node, indent_level=0):
        try:
            if visit_node.node_repr is not None:
                self.output.write(self.indent_str * indent_level)
                self.output.write(visit_node.node_repr)
                self.output.write('\n')
        except AttributeError:
            raise TreeWalkError("can't write visit_node: %s" % visit_node)

        for cn in visit_node.child_nodes:
            self.write_visit(cn, indent_level + 1)

    def build_text(self, ast_node):
        method_name = 'visitAST%s' % ast_node.__class__.__name__
        method = getattr(self, method_name, self.visitDefault)
        return method(ast_node)

    def visitASTTemplateNode(self, node):
        module_code = self.visitDefault(node)[0]
        if node.import_nodes:
            for n in node.import_nodes:
                module_code.extend(self.build_text(n))
        if node.from_nodes:
            for n in node.from_nodes:
                module_code.extend(self.build_text(n))
        if node.extends_nodes:
            for n in node.extends_nodes:
                module_code.extend(self.build_text(n))

        for n in node.attr_nodes:
            module_code.extend(self.build_text(n))

        for n in node.child_nodes:
            module_code.extend(self.build_text(n))

        # if we aren't extending a template, build out the main function
        if not node.extends_nodes and not node.library:
            module_code.extend(self.build_text(node.main_function))

        return [module_code]

    def visitASTExtendsNode(self, node):
        v = self.visitDefault(node)[0]
        for n in node.module_name_list:
            v.extend(self.build_text(n))
        return [v]

    visitASTImportNode = visitASTExtendsNode
    visitASTFromNode = visitASTExtendsNode
    visitASTAbsoluteExtendsNode = visitASTExtendsNode

    def visitASTCallFunctionNode(self, node):
        v = self.visitDefault(node)[0]
        v.append(VisitNode('expression', self.build_text(node.expression)))
        if node.arg_list:
            v.extend(self.build_text(node.arg_list))
        return [v]

    def visitASTCacheNode(self, node):
        v = self.visitDefault(node)[0]
        v.append(VisitNode('expression', self.build_text(node.expression)))
        return [v]

    def visitASTForNode(self, node):
        visit_node = self.visitDefault(node)[0]
        target_list = self.build_text(node.target_list)
        expression_list = self.build_text(node.expression_list)
        visit_node.extend(target_list)
        visit_node.extend(expression_list)
        for n in node.child_nodes:
            visit_node.extend(self.build_text(n))
        return [visit_node]

    def visitASTIfNode(self, node):
        if_node = self.visitDefault(node)[0]
        test_expression = VisitNode('test_expression',
                                    self.build_text(node.test_expression))
        if_node.append(test_expression)
        #if_node.append(VisitNode(str(node.scope)))
        for n in node.child_nodes:
            if_node.extend(self.build_text(n))
        visit_nodes = [if_node]
        if node.else_.child_nodes:
            else_visit_node = VisitNode('else')
            for n in node.else_.child_nodes:
                else_visit_node.extend(self.build_text(n))
            visit_nodes.append(else_visit_node)
        return visit_nodes

    def visitASTAttributeNode(self, node):
        v = self.visitDefault(node)[0]
        v.extend(self.build_text(node.default))
        return [v]

    def visitASTEchoNode(self, node):
        v = self.visitDefault(node)[0]
        for n in [node.test_expression, node.true_expression,
                  node.false_expression]:
            #print "visitASTParameterListNode:", n, text
            v.append(VisitNode(str(n)))
        return [v]

    def visitASTParameterListNode(self, node):
        v = self.visitDefault(node)[0]
        for n in node.child_nodes:
            #print "visitASTParameterListNode:", n, text
            v.append(VisitNode(str(n)))
        return [v]

    visitASTArgListNode = visitASTParameterListNode
    visitASTTargetListNode = visitASTParameterListNode
    visitASTExpressionListNode = visitASTParameterListNode
    visitASTListLiteralNode = visitASTParameterListNode
    visitASTTupleLiteralNode = visitASTParameterListNode

    def visitASTDictLiteralNode(self, node):
        v = self.visitDefault(node)[0]
        for n in node.child_nodes:
            key_expression, value_expression = n
            v.extend(self.build_text(key_expression))
            v.extend(self.build_text(value_expression))
        return [v]

    def visitASTParameterNode(self, node):
        if node.default:
            return [VisitNode('%s=%s' %
                              (node.name, ' '.join([self.generate_text(
                                  x) for x in self.build_text(node.default)])))]
        else:
            return [VisitNode('%s' % node.name)]

    def visitASTGetUDNNode(self, node):
        v = self.visitDefault(node)[0]
        v.extend(self.build_text(node.expression))
        return [v]

    visitASTGetAttrNode = visitASTGetUDNNode
    visitASTReturnNode = visitASTGetUDNNode
    visitASTPlaceholderSubstitutionNode = visitASTGetUDNNode
    visitASTBufferWrite = visitASTGetUDNNode

    def visitASTFilterNode(self, node):
        v = VisitNode('%s %s %s' %
                      (node.__class__.__name__, node.name, hash(node)))
        v.extend(self.build_text(node.expression))
        return [v]

    def visitASTSliceNode(self, node):
        v = self.visitDefault(node)[0]
        v.append(VisitNode('expression', self.build_text(node.expression)))
        v.append(VisitNode('slice', self.build_text(node.slice_expression)))
        return [v]

    def visitASTBinOpExpressionNode(self, node):
        v = self.visitDefault(node)[0]
        v.extend(self.build_text(node.left))
        v.append(VisitNode(node.operator))
        v.extend(self.build_text(node.right))
        return [v]

    visitASTBinOpNode = visitASTBinOpExpressionNode

    visitASTAssignNode = visitASTBinOpNode

    def visitASTUnaryOpNode(self, node):
        v = self.visitDefault(node)[0]
        v.append(VisitNode(node.operator))
        v.extend(self.build_text(node.expression))
        return [v]

    def visitASTFunctionNode(self, node):
        v = self.visitDefault(node)[0]
        if node.parameter_list:
            v.extend(self.build_text(node.parameter_list))
        #v.append(VisitNode(str(node.scope)))

        for n in node.child_nodes:
            v.extend(self.build_text(n))

        return [v]

    def visitASTDefNode(self, node):
        v = self.visitDefault(node)[0]
        if node.parameter_list:
            v.extend(self.build_text(node.parameter_list))

        for n in node.child_nodes:
            v.extend(self.build_text(n))

        return [v]

    visitASTBlockNode = visitASTDefNode

    def visitASTFragmentNode(self, node):
        v = self.visitDefault(node)[0]
        for n in node.child_nodes:
            v.extend(self.build_text(n))

        return [v]

    visitASTStripLinesNode = visitASTFragmentNode

    def visitASTDoNode(self, node):
        v = self.visitDefault(node)[0]
        v.extend(self.build_text(node.expression))
        return [v]

    def visitASTLiteralNode(self, node):
        return [VisitNode("%s '%r'" % (node.__class__.__name__, node.value))]

    visitASTTextNode = visitASTLiteralNode
    visitASTWhitespaceNode = visitASTLiteralNode
    visitASTOptionalWhitespaceNode = visitASTLiteralNode

    def visitDefault(self, node):
        return [VisitNode('%s %s' % (node.__class__.__name__, node.name))]

    def visitASTMacroNode(self, node):
        return [VisitNode('%s %s' % (node.__class__.__name__, node.value))]
