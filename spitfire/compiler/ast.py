# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import __builtin__
import copy
import traceback


# this is a horrible hack to let the tree modify itself during conversion
class EatPrevious(object):
    pass


class ASTNode(object):

    def __init__(self, name='', pos=None):
        self.name = name
        self.value = None
        self.parent = None
        self.child_nodes = NodeList()
        # optimization annotations
        self.hint_map = {}
        # Start and end position of a text or placeholder node within an I18n'd
        # message.
        self.start = self.end = None
        # tag items generated from a single line statment
        # this makes it easier to invent new ways to mangle optional whitespace
        self.statement = False
        # Position in the input string (measured in characters).
        self.pos = pos
        self.end_pos = None

    def __str__(self):
        if self.value:
            return '%s %s %r' % (self.__class__.__name__, self.name, self.value)
        return '%s %s' % (self.__class__.__name__, self.name)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, node):
        return bool(type(self) == type(
            node) and self.name == node.name and self.value == node.value and
                    self.child_nodes == node.child_nodes)

    def __hash__(self):
        return hash('%s%s%s%s' % (type(self), self.name, self.value,
                                  hash(tuple(self.child_nodes))))

    def getChildNodes(self):
        return [n for n in self.child_nodes if isinstance(n, ASTNode)]

    def append(self, node):
        if isinstance(node, list):
            self.extend(node)
        else:
            if type(node) is EatPrevious:
                del self.child_nodes[-1]
            else:
                try:
                    node.parent = self
                except AttributeError, e:
                    print e, node
                    raise
                self.child_nodes.append(node)

    def prepend(self, node):
        if isinstance(node, list):
            for n in reversed(node):
                self.child_nodes.insert(0, n)
        else:
            self.child_nodes.insert(0, node)

    # some classes override append() so just call down to that for now
    def extend(self, node_list):
        for n in node_list:
            self.append(n)

    def insert_before(self, marker_node, insert_node):
        """WARNING: If the same marker node appears more than once in the
        child_nodes list, the insert_node will be inserted before the first
        occurance."""
        try:
            idx = self.child_nodes.index(marker_node)
        except ValueError:
            raise ValueError("can't find child node %s in %s" %
                             (marker_node, self))
        # print ' '.join('insert_before', idx, id(self), self,
        #                id(marker_node), marker_node)
        insert_node.parent = self
        self.child_nodes.insert(idx, insert_node)

    def remove(self, node):
        self.replace(node, [])

    def replace(self, marker_node, insert_node_list):
        """Replace a node with another node or NodeList.

        If a NodeList is used, replace that child node with all of the
        nodes in the list. If it is just a basic node, replace the child
        node with that single node.
        """
        try:
            idx = self.child_nodes.index(marker_node)
        except ValueError:
            raise ValueError("can't find child node %s in %s" %
                             (marker_node, self))
        try:
            for n in reversed(insert_node_list):
                n.parent = self
                self.child_nodes.insert(idx, n)
        except TypeError:
            insert_node_list.parent = self
            self.child_nodes.insert(idx, insert_node_list)
        self.child_nodes.remove(marker_node)

    def copy(self, copy_children=True):
        if not copy_children:
            node = copy.copy(self)
            node.child_nodes = NodeList()
        else:
            node = copy.deepcopy(self)
        return node


class NodeList(list):

    def __init__(self, pos=None):
        # Position in the input string (measured in characters).
        self.pos = pos
        self.end_pos = None

    # note: need to iterate over a copy due to the way i modify the tree in-
    # place this is probably an indication that this approach is fundamentally
    # flawed
    def __iter__(self):
        return iter(list(list.__iter__(self)))

    def append(self, node):
        if isinstance(node, list):
            self.extend(node)
        else:
            list.append(self, node)

    def __hash__(self):
        # Equality is list equality.
        result = 0
        for item in self:
            result ^= hash(item)
        return result


class _ListNode(ASTNode):

    def __init__(self, parg_list=None, karg_list=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.parg_list = parg_list
        self.karg_list = karg_list
        if parg_list:
            self.extend(parg_list)
        else:
            self.parg_list = []

        if karg_list:
            self.extend(karg_list)
        else:
            self.karg_list = []

    def __len__(self):
        return len(self.child_nodes)

    def __iter__(self):
        return iter(self.child_nodes)

    def __str__(self):
        return '%s %s' % (ASTNode.__str__(self),
                          ', '.join(str(n) for n in self.child_nodes))

    def __getitem__(self, item):
        return self.child_nodes[item]

    def get_arg_map(self):
        arg_map = {}
        for parameter_node in self.child_nodes:
            if not isinstance(parameter_node, ParameterNode):
                continue
            if parameter_node.default:
                arg_map[parameter_node.name] = parameter_node.default.value
            else:
                arg_map[parameter_node.name] = NoParameter
        return arg_map

    def get_arg_node_map(self):
        arg_map = {}
        for parameter_node in self.child_nodes:
            if not isinstance(parameter_node, ParameterNode):
                continue
            if parameter_node.default:
                arg_map[parameter_node.name] = parameter_node.default
            else:
                arg_map[parameter_node.name] = NoParameter
        return arg_map

    def get_parg_list(self):
        return self.parg_list


class ArgListNode(_ListNode):
    pass


class BinOpNode(ASTNode):

    def __init__(self, operator, left, right, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.operator = operator
        self.left = left
        self.right = right

    def replace(self, node, replacement_node):
        if self.left is node:
            self.left = replacement_node
        elif self.right is node:
            self.right = replacement_node
        else:
            raise Exception("neither left nor right expression matches target")

    def __str__(self):
        return '%s (%s %s %s)' % (self.__class__.__name__, self.left,
                                  self.operator, self.right)

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.operator == node.operator
                    and self.left == node.left and self.right == node.right)

    def __hash__(self):
        return hash('%s%s%s%s' % (type(self), self.operator, hash(self.left),
                                  hash(self.right)))


# fixme: are both BinOpNode and BinOpExpressionNode needed?
class BinOpExpressionNode(BinOpNode):
    pass


class AssignNode(BinOpNode):

    def __init__(self, left, right, pos=None):
        BinOpNode.__init__(self, '=', left, right, pos=pos)


class BreakNode(ASTNode):
    pass


class DoNode(ASTNode):
    """This node allows for an expression to be treated like a statement.

    The result of the expression is ignored and not written to the buffer."""

    def __init__(self, expression=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        else:
            raise Exception("expression doesn't match replacement")

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.expression ==
                    node.expression and self.child_nodes == node.child_nodes)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), hash(self.expression),
                                hash(tuple(self.child_nodes))))

    def __str__(self):
        return '%s expr:%s' % (self.__class__.__name__, self.expression)


class SanitizedState(object):
    """An enum of sanitization states of the return value for a function call.

    SANITIZED_STRING: We know for sure that the return value is already filtered
    and is a string. Threrefore, we wrap the call in a SanitizedPlaceholder
    directly.

    SANITIZED: We know for sure that the return value is already filtered.
    Therefore, we wrap the call in mark_as_sanitized.

    UNKNOWN: We aren't sure if the return type is filtered. Therefore, we
    check for a skip_filter annotation on the function at runtime.

    UNSANITIZED: We are sure that the function does not return a filtered value
    so we should not do anything with the return value.

    NOT_OUTPUTTED: We know that the function output will not be stored in a
    variable or passed into another function. Therefore, we do not need to do
    anything with the return value.

    OUTPUTTED_IMMEDIATELY: We know that the result of the function will be used
    immediately, so the skip_filter information on the function will be
    sufficient and there is no need to wrap the result in a
    SanitizedPlaceholder.
    """
    SANITIZED_STRING = 1
    SANITIZED = 2
    UNKNOWN = 3
    UNSANITIZED = 4
    NOT_OUTPUTTED = 5
    OUTPUTTED_IMMEDIATELY = 6


class CallFunctionNode(ASTNode):

    def __init__(self, expression=None, arg_list=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression
        # Whether we're calling into a library template.
        self.library_function = False
        # What the current sanitized state is of the function call.
        # See SanitizedState.
        self.sanitization_state = SanitizedState.UNKNOWN
        if arg_list:
            self.arg_list = arg_list
        else:
            self.arg_list = ArgListNode()

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        else:
            raise Exception("expression doesn't match replacement")

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.library_function ==
                    node.library_function and self.expression == node.expression
                    and self.arg_list == node.arg_list and (
                        self.sanitization_state == node.sanitization_state
                    ) and self.child_nodes == node.child_nodes)

    def __hash__(self):
        return hash('%s%s%s%s%s' % (type(self), hash(self.library_function),
                                    hash(self.expression), hash(self.arg_list),
                                    hash(tuple(self.child_nodes))))

    def __str__(self):
        return '%s expr:%s arg_list:%s' % (self.__class__.__name__,
                                           self.expression, self.arg_list)


# encapsulate the idea that you want to write this to an output stream
# this is sort of an implicit function call, so the hierarchy makes some sense
class BufferWrite(CallFunctionNode):

    def append_text_node(self, node):
        if not (isinstance(node, BufferWrite) and
                isinstance(node.expression, LiteralNode)):
            raise Exception('node type mismatch')
        self.expression.value += node.expression.value


class BufferExtend(CallFunctionNode):
    """Class to batch writes to the buffer."""
    pass


class CacheNode(CallFunctionNode):

    def __init__(self, expression=None, pos=None):
        ASTNode.__init__(self, '_cph%08X' % unsigned_hash(expression), pos=pos)
        self.expression = expression

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.expression ==
                    node.expression)

    def __hash__(self):
        return hash('%s%s' % (type(self), hash(self.expression)))

    def __str__(self):
        return '%s expr:%s' % (self.__class__.__name__, self.expression)


class EchoNode(ASTNode):

    def __init__(self,
                 true_expression=None,
                 test_expression=None,
                 false_expression=None,
                 pos=None):
        ASTNode.__init__(self, pos=pos)
        self.true_expression = true_expression
        self.test_expression = test_expression
        self.false_expression = false_expression

    def replace(self, node, replacement_node):
        if self.true_expression is node:
            self.true_expression = replacement_node
        elif self.test_expression is node:
            self.test_expression = replacement_node
        elif self.false_expression is node:
            self.false_expression = replacement_node
        else:
            raise Exception("expression does not match target")


# dopey semi singleton - the nodes get cloned via deepcopy, so just
# make anything of this class identical
class __DefaultFilterFunction(object):

    def __eq__(self, o):
        return isinstance(o, self.__class__)

    def __hash__(self):
        return hash(self.__class__.__name__)


DefaultFilterFunction = __DefaultFilterFunction()


# encapsulate the idea that you want to run a filter over this expression
# this is sort of an implicit function call, so the hierarchy makes some sense
# again, in this case we want to preserve plenty of information and hierarchy
# for ease of optimization later on in the process
class FilterNode(ASTNode):

    def __init__(self,
                 expression=None,
                 filter_function_node=DefaultFilterFunction,
                 pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression
        self.filter_function_node = filter_function_node

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        else:
            raise Exception("expression doesn't match replacement")

    def __eq__(self, node):
        return bool(type(self) == type(
            node) and self.expression == node.expression and
                    self.filter_function_node == node.filter_function_node)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), hash(self.expression),
                                hash(self.filter_function_node)))

    def __str__(self):
        return '%s expr:%s %s' % (self.__class__.__name__, self.expression,
                                  hash(self))


class CommentNode(ASTNode):
    pass


class ContinueNode(ASTNode):
    pass


class DefNode(ASTNode):

    def __init__(self, *pargs, **kargs):
        ASTNode.__init__(self, *pargs, **kargs)
        self.parameter_list = ParameterListNode()

    def __str__(self):
        return '%s name:%s parameter_list:%s' % (self.__class__.__name__,
                                                 self.name, self.parameter_list)

    def __eq__(self, other):
        return bool(type(self) == type(other) and self.name == other.name and
                    self.parameter_list == other.parameter_list and
                    self.child_nodes == other.child_nodes)

    def __hash__(self):
        return hash('%s%s%s%s' % (type(self), hash(self.name),
                                  hash(tuple(self.parameter_list)),
                                  hash(tuple(self.child_nodes))))


class BlockNode(DefNode):
    pass


class MacroNode(DefNode):
    pass


class DictLiteralNode(ASTNode):

    def append(self, node):
        self.child_nodes.append(node)

    def insert_before(self, marker_node, insert_node):
        raise ValueError('unsupported insert_before')

    def replace(self, marker_node, insert_node_list):
        insert_node = insert_node_list
        try:
            insert_node.parent = self
        except AttributeError:
            raise AttributeError('no parent attribute on %s' % insert_node)
        for idx, (key_node, value_node) in enumerate(self.child_nodes):
            if marker_node == key_node:
                self.child_nodes[idx] = (insert_node, value_node)
                break
            elif marker_node == value_node:
                self.child_nodes[idx] = (key_node, insert_node)
                break
        else:
            raise ValueError("can't find child node %s in %s" %
                             (marker_node, self))


class ExpressionListNode(_ListNode):
    pass


class ForNode(ASTNode):

    def __init__(self, target_list=None, expression_list=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        if target_list:
            self.target_list = target_list
        else:
            self.target_list = TargetListNode()
        if expression_list:
            self.expression_list = expression_list
        else:
            self.expression_list = ExpressionListNode()
        self.scope = Scope('ForNode')
        self.loop_variant_set = None

    def __str__(self):
        return (
            '%s target_list:%s expr_list:%s' %
            (self.__class__.__name__, self.target_list, self.expression_list))


class StripLinesNode(ASTNode):
    """These are thrown away by the analyzer and do not make it to the
    codegen stage."""


class FunctionNode(ASTNode):

    def __init__(self, *pargs, **kargs):
        ASTNode.__init__(self, *pargs, **kargs)

        # PSEUDOCODE moved to codegen phase
        self.parameter_list = ParameterListNode()
        self.scope = Scope('Function')

    def __str__(self):
        return '%s %s parameter_list:%r' % (self.__class__.__name__, self.name,
                                            self.parameter_list)


class GetAttrNode(ASTNode):

    def __init__(self, expression, name, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression
        self.name = name

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.name == node.name and
                    self.expression == node.expression)

    def __hash__(self):
        return hash('%s%s%s' %
                    (type(self), hash(self.name), hash(self.expression)))

    def __str__(self):
        return '%s expr:%s . name:%s' % (self.__class__.__name__,
                                         self.expression, self.name)

    def getChildNodes(self):
        child_nodes = self.expression.getChildNodes()
        child_nodes.append(self.expression)
        if isinstance(self.name, ASTNode):
            child_nodes.append(self.name)
        return child_nodes

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        else:
            raise Exception("expression doesn't match replacement")


class GetUDNNode(GetAttrNode):
    pass


class IdentifierNode(ASTNode):
    # all subclasses of IdentifierNode should be treated as equivalent
    def __eq__(self, node):
        return bool(isinstance(node, IdentifierNode) and self.name == node.name)

    def __hash__(self):
        return hash(self.name)


class TemplateMethodIdentifierNode(IdentifierNode):
    pass


class IfNode(ASTNode):

    def __init__(self, test_expression=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.test_expression = test_expression
        self.else_ = ElseNode(self)
        self.scope = Scope('If')

    def replace(self, node, replacement_node):
        if self.test_expression is node:
            self.test_expression = replacement_node
        else:
            ASTNode.replace(self, node, replacement_node)

    def __str__(self):
        return '%s test_expr:%s\nScope:%s\nelse:\n  %s' % (
            self.__class__.__name__, self.test_expression, self.scope,
            self.else_)

    def __eq__(self, other):
        return bool(type(self) == type(
            other) and self.test_expression == other.test_expression and
                    self.else_ == other.else_ and self.scope == other.scope and
                    self.child_nodes == other.child_nodes)

    def __hash__(self):
        return hash("%s%s%s%s%s" %
                    (type(self), hash(self.test_expression), hash(self.else_),
                     hash(self.scope), hash(self.child_nodes)))


class ElseNode(ASTNode):

    def __init__(self, parent=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.parent = parent
        self.scope = Scope('Else')

    def __str__(self):
        return '%s %s' % (self.__class__.__name__, hash(self))


class ImplementsNode(ASTNode):
    pass


class AllowUndeclaredGlobalsNode(ASTNode):
    pass


class LooseResolutionNode(ASTNode):
    pass


class AllowRawNode(ASTNode):
    pass


class ImportNode(ASTNode):

    def __init__(self, module_name_list, library=False, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.module_name_list = module_name_list
        self.library = library
        # in case you have a different target, save a copy of the
        # orginal name to use for dependency analysis
        self.source_module_name_list = module_name_list[:]

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.library == node.library
                    and self.module_name_list == node.module_name_list)

    def __hash__(self):
        return hash('%s%s' % (type(self), hash(tuple(self.module_name_list))))

    def __str__(self):
        return ('%s module_name_list:%r' %
                (self.__class__.__name__, self.module_name_list))


# alpha break
class ExtendsNode(ImportNode):
    pass


class AbsoluteExtendsNode(ExtendsNode):
    pass


class FromNode(ImportNode):

    def __init__(self,
                 module_name_list,
                 identifier,
                 alias=None,
                 library=False,
                 pos=None):
        ImportNode.__init__(self, module_name_list, library=library, pos=pos)
        self.identifier = identifier
        self.alias = alias

    def __eq__(self, node):
        return bool(type(self) == type(
            node) and self.module_name_list == node.module_name_list and
                    self.identifier == node.identifier)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), hash(tuple(self.module_name_list)),
                                self.identifier))

    def __str__(self):
        return ('%s module_name_list:%r identifier:%s' %
                (self.__class__.__name__, self.module_name_list,
                 self.identifier))


class ListLiteralNode(ASTNode):

    def __str__(self):
        return '%s nodes:%r' % (self.__class__.__name__, self.child_nodes)


class LiteralNode(ASTNode):

    def __init__(self, value, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.value = value

    def __str__(self):
        return '%s value:%r' % (self.__class__.__name__, self.value)


class GlobalNode(ASTNode):
    pass


class ParameterNode(ASTNode):

    def __init__(self, name, default=None, pos=None):
        ASTNode.__init__(self, name, pos=pos)
        self.default = default

    def replace(self, node, replacement_node):
        if self.default is node:
            self.default = replacement_node
        else:
            raise Exception("default expression does not match target")

    def __str__(self):
        return '%s %s' % (ASTNode.__str__(self), self.default)

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.name == node.name and
                    self.default == node.default)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), self.name, hash(self.default)))


class AttributeNode(ParameterNode):
    pass


class FilterAttributeNode(AttributeNode):
    pass


class __NoParameter(object):

    def __repr__(self):
        return '<NoParameter>'


NoParameter = __NoParameter()


class ParameterListNode(_ListNode):
    pass


class PlaceholderNode(ASTNode):
    pass


class PlaceholderSubstitutionNode(ASTNode):

    def __init__(self, expression, parameter_list=None, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression
        if parameter_list is None:
            self.parameter_list = ParameterListNode()
        else:
            self.parameter_list = parameter_list

    def __str__(self):
        return '%s expr:%r %s' % (self.__class__.__name__, self.expression,
                                  self.parameter_list)


class ReturnNode(ASTNode):

    def __init__(self, expression, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression

    def __str__(self):
        return '%s expr:%r' % (self.__class__.__name__, self.expression)


class SliceNode(ASTNode):

    def __init__(self, expression, slice_expression, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.expression = expression
        self.slice_expression = slice_expression

    def __str__(self):
        return (
            '%s expr:%s [ %s ]' %
            (self.__class__.__name__, self.expression, self.slice_expression))

    def __eq__(self, node):
        return bool(type(self) == type(
            node) and self.expression == node.expression and
                    self.slice_expression == node.slice_expression)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), hash(self.expression),
                                hash(self.slice_expression)))

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        elif self.slice_expression is node:
            self.slice_expression = replacement_node
        else:
            raise Exception("neither expression matches target")


class TargetNode(IdentifierNode):
    pass


class TargetListNode(_ListNode):
    pass


class TextNode(ASTNode):

    def __init__(self, value, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.value = value

    def append_text_node(self, node):
        if not isinstance(node, TextNode):
            raise Exception('node type mismatch')
        self.value += node.value

    def __eq__(self, other):
        return bool(type(self) == type(other) and self.value == other.value)

    def __hash__(self):
        return hash("%s%s" % (type(self), self.value))


class WhitespaceNode(TextNode):

    def make_optional(self):
        return OptionalWhitespaceNode(self.value)


class NewlineNode(WhitespaceNode):
    pass


class OptionalWhitespaceNode(WhitespaceNode):
    pass


class FragmentNode(ASTNode):
    pass


class TemplateNode(ASTNode):
    __builtin_set = frozenset(dir(__builtin__))

    def __init__(self, classname=None, pos=None, **kargs):
        ASTNode.__init__(self, pos=pos, **kargs)
        self.source_path = None
        # fixme: need to get the classname from somewhere else
        self.classname = classname
        self.main_function = FunctionNode(name='main')
        self.main_function.parameter_list = ParameterListNode()
        self.main_function.parameter_list.append(ParameterNode(name='self'))
        self.encoding = 'utf-8'
        self.extends_nodes = NodeList()
        self.import_nodes = NodeList()
        self.from_nodes = NodeList()
        self.attr_nodes = NodeList()
        self.library = False
        self.implements = False
        self.allow_undeclared_globals = False
        self.use_loose_resolution = False
        self.baked = False
        self.explicitly_allow_raw = False
        self.global_placeholders = set()
        self.global_identifiers = set()
        self.cached_identifiers = set()
        self.template_methods = set()
        self.library_identifiers = set()
        self.trusted_module_identifiers = set()
        self.local_scope_identifiers = set()
        self.used_function_registry_identifiers = set()

    def __str__(self):
        return '%s\nimport:%s\nfrom:%s\nextends:%s\nmain:%s' % (
            self.__class__.__name__, self.import_nodes, self.from_nodes,
            self.extends_nodes, self.main_function)

    def has_identifier(self, name):
        return (name in self.__builtin_set or
                name in self.local_scope_identifiers or
                name in self.template_methods or
                name in self.trusted_module_identifiers or
                name in [node.name for node in self.attr_nodes])


class TupleLiteralNode(ASTNode):
    pass


class UnaryOpNode(ASTNode):

    def __init__(self, operator, expression, pos=None):
        ASTNode.__init__(self, pos=pos)
        self.operator = operator
        self.expression = expression

    def replace(self, node, replacement_node):
        if self.expression is node:
            self.expression = replacement_node
        else:
            raise Exception("expression does not match target")

    def __eq__(self, node):
        return bool(type(self) == type(node) and self.name == node.name and
                    self.expression == node.expression)

    def __hash__(self):
        return hash('%s%s%s' % (type(self), self.name, self.expression))


# save state related to scoping rules for code blocks
# this is kind of a hack. i am semi-emulating python scoping rules, which are
# a bit funky. probably, i should have defined a set of scope rules for
# templates and shoe-horned that into python
class Scope(object):

    def __init__(self, name=None):
        if name:
            self.name = name
        else:
            self.name = hex(id(self))
        self.local_identifiers = set()
        self.aliased_expression_map = OrderedDict()
        self.alias_name_set = ScopeSet()
        self.filtered_expression_map = {}
        self.hoisted_aliases = []
        # This set holds local identifiers that may or may not be defined
        # in the current scope. For example a variable defined in only the
        # if or the else clause of an if statement.
        self.partial_local_identifiers = set()
        # This set holds the local identifiers that are marked as dirty
        # (i.e. they have been used).
        self.dirty_local_identifiers = set()

    def __str__(self):
        return "<Scope %(name)s> %(alias_name_set)s" % vars(self)

    def __eq__(self, other):
        # TODO: Is this accurate enough?
        return (type(self) == type(other) and self.name == other.name and
                self.local_identifiers == other.local_identifiers)

    def __hash__(self):
        # local_identifiers is not hashable.
        return hash("%s%s" % (type(self), self.name))


class ScopeSet(set):
    pass
    #def add(self, o):
    #  set.add(self, o)


class OrderedDict(object):

    def __init__(self):
        self._dict = {}
        self._order = []

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def __contains__(self, key):
        return key in self._dict

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        if key not in self._dict:
            self._order.append(key)
            self._dict[key] = value

    def __delitem__(self, key):
        self._order.remove(key)
        del self._dict[key]

    def keys(self):
        return list(self.iterkeys())

    def items(self):
        return list(self.iteritems())

    def iterkeys(self):
        return iter(self._order)

    def iteritems(self):
        for key in self._order:
            yield key, self._dict[key]

    def update(self, ordered_dict):
        for key, value in ordered_dict.iteritems():
            self[key] = value

    def __str__(self):
        return str([(x, self._dict[x]) for x in self._order])


# this is sort of a hack to support optional white space nodes inside the
# parse tree.  the reality is that this probably requires a more complex
# parser, but we can get away with faking it for now.
def make_optional(node_list):
    try:
        if type(node_list[-1]) == WhitespaceNode:
            if (len(node_list) == 1 or type(node_list[-2]) == NewlineNode or
                    node_list[-2].statement or
                    not isinstance(node_list[-2],
                                   (TextNode, PlaceholderSubstitutionNode))):
                node_list[-1] = OptionalWhitespaceNode(node_list[-1].value)
    except IndexError:
        pass


# this is another hack to support line-wise stripping of white space nodes
# inside a #strip_lines directive.
def strip_whitespace(node_list, starts_new_line=True):
    # starts as optional only if we're at the beginning of a new line.
    optional = starts_new_line
    for i, node in enumerate(node_list):
        if isinstance(node, (OptionalWhitespaceNode, NewlineNode)):
            optional = True
            node_list[i] = OptionalWhitespaceNode('')
        elif isinstance(node, WhitespaceNode):
            if optional:
                node_list[i] = OptionalWhitespaceNode('')
            elif len(node_list) > i + 1 and isinstance(node_list[i + 1],
                                                       NewlineNode):
                optional = True
                node_list[i] = OptionalWhitespaceNode('')
        elif isinstance(node, TextNode):
            if optional:
                node.value = node.value.lstrip()
            optional = False
        elif not (node.statement or node.child_nodes or isinstance(
                node, CommentNode)):
            optional = False

        if optional and i > 0:
            prev_node = node_list[i - 1]
            if isinstance(prev_node, TextNode):
                prev_node.value = prev_node.value.rstrip()


def unsigned_hash(x):
    exp_hash = hash(x)
    if exp_hash < 0:
        exp_hash = -exp_hash | 0x80000000
    return exp_hash


def track_line_numbers(exempt_methods=()):
    """Class decorator: Change a parser class to track line numbers in
    the AST nodes returned by the given grammar rules.

    This will wrap all methods except the ones starting with an underscore
    or that are explicitly exempt.
    """

    def make_execute_rule(rule):

        def _execute_rule(self, *args, **kwargs):
            saved_position = self.file_position
            result = rule(self, *args, **kwargs)
            if isinstance(result, (ASTNode, NodeList)):
                result.pos = saved_position
                result.end_pos = self.file_position
            return result

        return _execute_rule

    def decorator(cls):
        for method_name in dir(cls):
            if method_name in exempt_methods or method_name.startswith('_'):
                continue
            rule = getattr(cls, method_name)
            if hasattr(rule, '__call__'):
                setattr(cls, method_name, make_execute_rule(rule))
        return cls

    return decorator

# This is a list of all of the nodes that are considered statements.
# They can not appear on the right hand of an assignment. This list is
# used to determine if a node should be moved out of the expression
# field of another node.
statement_nodes = (AbsoluteExtendsNode, AllowUndeclaredGlobalsNode, AssignNode,
                   BlockNode, BufferExtend, BufferWrite, CommentNode,
                   ContinueNode, DefNode, DoNode, EchoNode, ElseNode,
                   ExtendsNode, ForNode, FromNode, FunctionNode, GlobalNode,
                   IfNode, ImplementsNode, ImportNode, LooseResolutionNode,
                   MacroNode, ReturnNode, StripLinesNode, TextNode)
