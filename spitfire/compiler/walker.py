class TreeWalkError(Exception):
  pass


def print_tree(root):
  print TreeVisitor(root).get_text()
    
# perform an in-order traversal of the AST and call the generate methods
class TreeVisitor(object):
  def __init__(self, root):
    self.root = root

  def walk(self, node=None):
    if node is None:
      node = self.root
    method_name = 'visitAST%s' % node.__class__.__name__
    getattr(self, method_name, self.visitDefault)(node)

  def visitDefault(self, node):
    pass
    
  def visitASTTemplateNode(self, node):
    self.visitDefault(node)
    if node.import_nodes:
      for n in node.import_nodes:
        self.walk(n)
    if node.from_nodes:
      for n in node.from_nodes:
        self.walk(n)
    if node.extends_nodes:
      for n in node.extends_nodes:
        self.walk(n)
    for n in node.attr_nodes:
      self.walk(n)
    
    for n in node.child_nodes:
      self.walk(n)

    # if we aren't extending a template, build out the main function
    self.walk(node.main_function)

  def visitASTExtendsNode(self, node):
    self.visitDefault(node)
    for n in node.module_name_list:
      self.walk(n)

  visitASTImportNode = visitASTExtendsNode
  visitASTFromNode = visitASTExtendsNode
  visitASTAbsoluteExtendsNode = visitASTExtendsNode
  
  def visitASTCallFunctionNode(self, node):
    self.visitDefault(node)
    self.walk(node.expression)
    if node.arg_list:
      self.walk(node.arg_list)

  def visitASTForNode(self, node):
    self.visitDefault(node)
    self.walk(node.target_list)
    self.walk(node.expression_list)
    for n in node.child_nodes:
      self.walk(n)

  def visitASTIfNode(self, node):
    self.visitDefault(node)
    self.walk(node.test_expression)
    for n in node.child_nodes:
      self.walk(n)
    if node.else_.child_nodes:
      self.visitDefault(node.else_)
      for n in node.else_.child_nodes:
        self.walk(n)

  def visitASTAttributeNode(self, node):
    self.visitDefault(node)
    self.walk(node.default)
    
  def visitASTParameterListNode(self, node):
    self.visitDefault(node)
    for n in node.child_nodes:
      self.walk(n)

  visitASTArgListNode = visitASTParameterListNode
  visitASTTargetListNode = visitASTParameterListNode
  visitASTExpressionListNode = visitASTParameterListNode
  visitASTListLiteralNode = visitASTParameterListNode
  visitASTTupleLiteralNode = visitASTParameterListNode

  def visitASTDictLiteralNode(self, node):
    self.visitDefault(node)
    for key_expression, value_expression in node.child_nodes:
      self.walk(key_expression)
      self.walk(value_expression)

  def visitASTParameterNode(self, node):
    self.visitDefault(node)
    if node.default:
      self.walk(node.default)
    
  def visitASTGetUDNNode(self, node):
    self.visitDefault(node)
    self.walk(node.expression)

  visitASTGetAttrNode = visitASTGetUDNNode
  visitASTReturnNode = visitASTGetUDNNode
  visitASTPlaceholderSubstitutionNode = visitASTGetUDNNode
  visitASTBufferWrite = visitASTGetUDNNode
  visitASTFilterNode = visitASTGetUDNNode
  visitASTUnaryOpNode = visitASTGetUDNNode

  def visitASTSliceNode(self, node):
    self.visitDefault(node)
    self.walk(node.expression)
    self.walk(node.slice_expression)

  def visitASTBinOpExpressionNode(self, node):
    self.visitDefault(node)
    self.walk(node.left)
    self.walk(node.right)
  visitASTBinOpNode = visitASTBinOpExpressionNode
  visitASTAssignNode = visitASTBinOpNode
  
  def visitASTFunctionNode(self, node):
    self.visitDefault(node)
    if node.parameter_list:
      self.walk(parameter_list)

    for n in node.child_nodes:
      self.walk(n)

  visitASTDefNode = visitASTFunctionNode

  def visitASTFragmentNode(self, node):
    self.visitDefault(node)
    for n in node.child_nodes:
      self.walk(n)

  def visitASTLiteralNode(self, node):
    self.visitDefault(node)
  visitASTTextNode = visitASTLiteralNode  
  visitASTWhitespaceNode = visitASTLiteralNode  
  visitASTOptionalWhitespaceNode = visitASTLiteralNode  


# flatten a tree into an in-order list
class ClearCutter(TreeVisitor):
  def __init__(self, *pargs):
    TreeVisitor.__init__(self, *pargs)
    self.node_list = []

  def visitDefault(self, node):
    self.node_list.append(node)

def flatten_tree(node):
  cc = ClearCutter(node)
  cc.walk()
  return cc.node_list
  
