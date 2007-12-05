import copy

# this is a horrible hack to let the tree modify itself during conversion
class EatPrevious(object):
  pass

class ASTNode(object):
  def __init__(self, name=''):
    self.name = name
    self.value = None
    self.parent = None
    self.child_nodes = NodeList()
    # optimization annotations
    self.hint_map = {}

  def __str__(self):
    if self.value:
      return '%s %s %r' % (self.__class__.__name__, self.name, self.value)
    return '%s %s' % (self.__class__.__name__, self.name)

  def __repr__(self):
    return self.__str__()

  def __eq__(self, node):
    return bool(type(self) == type(node) and
                self.name == node.name and
                self.value == node.value and
                self.child_nodes == node.child_nodes)

  def __hash__(self):
    return hash('%s%s%s%s' %
                (type(self), self.name, self.value, hash(tuple(self.child_nodes))))

  def getChildNodes(self):
    return [n for n in self.child_nodes if isinstance(n, ASTNode)]
  
  def append(self, node):
    if isinstance(node, list):
      self.extend(node)
    else:
      if type(node) is EatPrevious:
        del self.child_nodes[-1]
      else:
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
    idx = self.child_nodes.index(marker_node)
    self.child_nodes.insert(idx, insert_node)

  def replace(self, marker_node, insert_node_list):
    print "replace", type(self)
    idx = self.child_nodes.index(marker_node)
    try:
      for n in reversed(insert_node_list):
        self.child_nodes.insert(idx, n)
    except TypeError:
      self.child_nodes.insert(idx, insert_node_list)
    self.child_nodes.remove(marker_node)

  def copy(self, copy_children=True):
    node = copy.deepcopy(self)
    if not copy_children:
      node.child_nodes = NodeList()
    return node

class NodeList(list):
  def append(self, node):
    if isinstance(node, list):
      self.extend(node)
    else:
      list.append(self, node)
  

class _ListNode(ASTNode):
  def __init__(self, parg_list=None, karg_list=None):
    ASTNode.__init__(self)
    if parg_list:
      self.extend(parg_list)
    if karg_list:
      self.extend(karg_list)

  def __iter__(self):
    return iter(self.child_nodes)
    
  def __str__(self):
    return '%s %s' % (ASTNode.__str__(self),
                      ', '.join(str(n) for n in self.child_nodes))

class ArgListNode(_ListNode):
  pass

class BinOpNode(ASTNode):
  def __init__(self, operator, left, right):
    ASTNode.__init__(self)
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
    return '%s (%s %s %s)' % (
      self.__class__.__name__, self.left, self.operator, self.right)

class BinOpExpressionNode(BinOpNode):
  pass

class AssignNode(BinOpNode):
  def __init__(self, left, right):
    BinOpNode.__init__(self, '=', left, right)

class BreakNode(ASTNode):
  pass

class CallFunctionNode(ASTNode):
  def __init__(self, expression=None, arg_list=None):
    ASTNode.__init__(self)
    self.expression = expression
    if arg_list:
      self.arg_list = arg_list
    else:
      self.arg_list = ArgListNode()

  def replace(self, node, replacement_node):
    if self.expression is node:
      self.expression = replacement_node
    else:
      raise Exception("expression doesn't mactch replacement")
    
  def __str__(self):
    return '%s expr:%s arg_list:%s' % (
      self.__class__.__name__, self.expression, self.arg_list)

class CommentNode(ASTNode):
  pass

class ContinueNode(ASTNode):
  pass

class DefNode(ASTNode):
  def __init__(self, *pargs, **kargs):
    ASTNode.__init__(self, *pargs, **kargs)
    self.parameter_list = ParameterListNode()
    
  def __str__(self):
    return '%s name:%s parameter_list:%s' % (
      self.__class__.__name__, self.name, self.parameter_list)

class BlockNode(DefNode):
  pass

class ExpressionListNode(_ListNode):
  pass


class ForNode(ASTNode):
  def __init__(self, target_list=None, expression_list=None):
    ASTNode.__init__(self)
    if target_list:
      self.target_list = target_list
    else:
      self.target_list = TargetListNode()
    if expression_list:
      self.expression_list = expression_list
    else:
      self.expression_list = ExpressionListNode()

  def __str__(self):
    return ('%s target_list:%s expr_list:%s' %
            (self.__class__.__name__, self.target_list, self.expression_list))

# fixme: why is this necessary?
class FunctionInitNode(ASTNode):
  pass

class FunctionNode(ASTNode):
  def __init__(self, *pargs, **kargs):
    ASTNode.__init__(self, *pargs, **kargs)
    new_buffer = CallFunctionNode(
          GetAttrNode(IdentifierNode('self'), 'new_buffer'))

    self.child_nodes = [
      AssignNode(
        AssignIdentifierNode('buffer'),
        new_buffer),
      ReturnNode(
        CallFunctionNode(GetAttrNode(IdentifierNode('buffer'), 'getvalue'))),
      ]
    self.parameter_list = ParameterListNode()
    
  def append(self, node):
    self.child_nodes.insert(-1, node)

  def __str__(self):
    return '%s parameter_list:%r' % (
      self.__class__.__name__, self.parameter_list)


class GetAttrNode(ASTNode):
  def __init__(self, expression, name):
    ASTNode.__init__(self)
    self.expression = expression
    self.name = name

  def __eq__(self, node):
    return bool(type(self) == type(node) and
                self.name == node.name and
                self.expression == node.expression)

  def __hash__(self):
    return hash('%s%s%s' %
                (type(self), self.name, self.expression))

  def __str__(self):
    return '%s expr:%s . name:%s' % (
      self.__class__.__name__, self.expression, self.name)

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
      raise Exception("expression doesn't mactch replacement")

class GetUDNNode(GetAttrNode):
  pass

class IdentifierNode(ASTNode):
  # all subclasses of IdentifierNode should be treated as equivalent
  def __eq__(self, node):
    return bool(isinstance(node, IdentifierNode) and
                self.name == node.name)

  def __hash__(self):
    return hash(self.name)

class AssignIdentifierNode(IdentifierNode):
  pass

class IfNode(ASTNode):
  def __init__(self, test_expression=None):
    ASTNode.__init__(self)
    self.test_expression = test_expression
    self.else_ = NodeList()

  def replace(self, node, replacement_node):
    if self.test_expression is node:
      self.test_expression = replacement_node
    else:
      ASTNode.replace(self, node, replacement_node)
    
  def __str__(self):
    return '%s test_expr:%s\nelse:\n  %s' % (
      self.__class__.__name__, self.test_expression, self.else_)

class ImplementsNode(ASTNode):
  pass

class ImportNode(ASTNode):
  def __init__(self, module_name_list):
    ASTNode.__init__(self)
    self.module_name_list = module_name_list

  def __str__(self):
    return ('%s module_name_list:%r' %
        (self.__class__.__name__, self.module_name_list))

# alpha break
class ExtendsNode(ImportNode):
  pass

class FromNode(ImportNode):
  def __init__(self, module_name_list, identifier):
    ImportNode.__init__(self, module_name_list)
    self.identifier = identifier
    
  def __str__(self):
    return ('%s module_name_list:%r identifier:%s' %
        (self.__class__.__name__, self.module_name_list,
         self.identifier))

class ListLiteralNode(ASTNode):
  def __str__(self):
    return '%s nodes:%r' % (self.__class__.__name__, self.child_nodes)

class LiteralNode(ASTNode):
  def __init__(self, value):
    ASTNode.__init__(self)
    self.value = value

  def __str__(self):
    return '%s value:%r' % (self.__class__.__name__, self.value)


class ParameterNode(ASTNode):
  def __init__(self, name, default=None):
    ASTNode.__init__(self, name)
    self.default = default

  def __str__(self):
    return '%s %s' % (ASTNode.__str__(self), self.default)

class AttributeNode(ParameterNode):
  pass

class ParameterListNode(_ListNode):
  pass

class PlaceholderNode(ASTNode):
  pass

class PlaceholderSubstitutionNode(ASTNode):
  def __init__(self, expression):
    ASTNode.__init__(self)
    self.expression = expression

  def __str__(self):
    return '%s expr:%r' % (self.__class__.__name__, self.expression)

class ReturnNode(ASTNode):
  def __init__(self, expression):
    ASTNode.__init__(self)
    self.expression = expression

  def __str__(self):
    return '%s expr:%r' % (self.__class__.__name__, self.expression)

class SliceNode(ASTNode):
  def __init__(self, expression, slice_expression):
    ASTNode.__init__(self)
    self.expression = expression
    self.slice_expression = slice_expression

  def __str__(self):
    return ('%s expr:%s [ %s ]' %
            (self.__class__.__name__, self.expression, self.slice_expression))

class TargetNode(IdentifierNode):
  pass

class TargetListNode(_ListNode):
  pass

class TextNode(ASTNode):
  def __init__(self, value):
    ASTNode.__init__(self)
    self.value = value

  def append_text_node(self, node):
    if not isinstance(node, TextNode):
      raise Exception('node type mismatch')
    self.value += node.value

class NewlineNode(TextNode):
  pass

class WhitespaceNode(TextNode):
  def make_optional(self):
    return OptionalWhitespaceNode(self.value)

class OptionalWhitespaceNode(TextNode):
  pass

class TemplateNode(ASTNode):
  library = False
  def __init__(self, classname=None, **kargs):
    ASTNode.__init__(self, **kargs)
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
  
  def __str__(self):
    return '%s\nimport:%s\nfrom:%s\nextends:%s\nmain:%s' % (
      self.__class__.__name__,
      self.import_nodes,
      self.from_nodes,
      self.extends_nodes,
      self.main_function)
  
class TupleLiteralNode(ASTNode):
  pass

class UnaryOpNode(ASTNode):
  def __init__(self, operator, expression):
    ASTNode.__init__(self)
    self.operator = operator
    self.expression = expression

# this is sort of a hack to support optional white space nodes inside the
# parse tree.  the reality is that this probably requires a more complex
# parser, but we can get away with examining the node stake to fake it for now.
def make_optional(node_list):
  try:
    if type(node_list[-1]) == WhitespaceNode:
      if len(node_list) == 1 or type(node_list[-2]) == NewlineNode:
        node_list[-1] = OptionalWhitespaceNode(node_list[-1].value)
  except IndexError:
    pass
