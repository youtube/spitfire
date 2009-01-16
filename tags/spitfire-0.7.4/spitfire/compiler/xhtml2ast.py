import traceback
import xml.dom.minidom

from spitfire.compiler.ast import *

import spitfire.compiler.util

enable_debug = False
def debug(func_name, dom_node):
  if not enable_debug:
    return
  if dom_node.attributes:
    print func_name, dom_node.nodeName, dom_node.attributes.keys()
  else:
    print func_name, dom_node.nodeName
  
class XHTML2AST(object):
  namespace = 'py'
  attr_op_namespace = 'pyattr'
  
  def build_template(self, filename):
    f = open(filename)
    data = f.read().decode('utf8')
    f.close()
    return self.parse(data)

  def parse(self, src_text):
    dom = xml.dom.minidom.parseString(src_text)
    template = TemplateNode()
    template.extend(self.build_ast(dom))
    return template
  
  def build_ast(self, dom_node):
    debug('build_ast', dom_node)

    node_list = []
    
    if dom_node.attributes:
      # the key types have a precedence that needs to be preserved
      # www.zope.org/Documentation/Books/ZopeBook/2_6Edition/AppendixC.stx
      # since this is also how we scan the tree, on-error is included
      # fixme: content/replace are mutually exclusive, that should generate an
      # error
      # the thing is, the way we process things is a little complicated, so
      # the order is actually different - we might handle something like
      # omit-tag early on, but really only apply it's implications later on
      op_precedence = [
        'omit-tag',
        'define',
        'condition',
        'repeat',
        'content',
        'content-html',
        'replace',
        'replace-html',
        'attributes',
        'on-error',
        ]

      # some of these operations can alter the output stream (most of them
      # really) - also, some don't exactly make sense to be on the same object
      # as a repeat - for instance, repeat->replace, whereas repeat->attributes
      # makes more sense

      # fixme: do I need keys() here? also, i think that attribute can be None
      attr_name_list = dom_node.attributes.keys()
      processed_any_op = False
      for op in op_precedence:
        op_attr_name = '%s:%s' % (self.namespace, op)
        if dom_node.hasAttribute(op_attr_name): # in attr_name_list:
          op_handler = 'handle_%s' % op
          op_handler = op_handler.replace('-', '_')
          # print "op_handler:", op_handler, dom_node.nodeName, dom_node.attributes.keys(), processed_any_op

          node_list.extend(getattr(self, op_handler)(dom_node, op_attr_name))
          processed_any_op = True

      # process attribute namespace
      attr_output_ast = []
      attr_prune_list = []
      # this is horribly un-pythonic - i'm having Java flashbacks
      for i in xrange(dom_node.attributes.length):
        attr = dom_node.attributes.item(i)
        if attr.prefix == self.attr_op_namespace:
          attr_prune_list.append(attr.localName)
          attr_prune_list.append('%s:%s' % (self.attr_op_namespace,
                                            attr.localName))
          attr_output_ast.extend(self.make_attr_node(attr))
          # print "attr_handler:", attr.prefix, attr.localName
          #processed_any_op = True
      for attr_name in attr_prune_list:
        try:
          dom_node.removeAttribute(attr_name)
        except xml.dom.NotFoundErr:
          print "ignoring missing", attr_name

      if not processed_any_op:
        node_list.extend(self.handle_default(dom_node,
                                             attr_ast=attr_output_ast))
    else:
      node_list.extend(self.handle_default(dom_node))

    #for child in dom_node.childNodes:
    #  node_list.extend(self.build_ast(child))

    return node_list

  # attr_ast - allow injecting some ast nodes
  # fixme: feels like it could have a cleaner API
  def handle_default(self, dom_node, attr_ast=None):
    debug('handle_default', dom_node)
    node_list = []
    if dom_node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
      node_list.extend(self.make_tag_node(dom_node, attr_ast=attr_ast))
      for child in dom_node.childNodes:
        node_list.extend(self.build_ast(child))
      node_list.extend(self.make_tag_node(dom_node, close=True))
    elif dom_node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
      node_list.append(TextNode(dom_node.nodeValue))
    elif dom_node.nodeType == xml.dom.minidom.Node.COMMENT_NODE:
      # node_list.append(TextNode(dom_node.nodeValue))
      pass
    elif dom_node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
      for child in dom_node.childNodes:
        node_list.extend(self.build_ast(child))
    elif dom_node.nodeType == xml.dom.minidom.Node.PROCESSING_INSTRUCTION_NODE:
      if dom_node.nodeName == 'py-doctype':
        node_list.append(TextNode(dom_node.nodeValue))
      else:
        raise Exception("unexepected processing instruction: %s" % dom_node)
    else:
      raise Exception("unexepected node type: %s" % dom_node.nodeType)
    return node_list

  def make_tag_node(self, dom_node, close=False, attr_ast=None):
    debug("make_tag_node", dom_node)
    node_list = []
    node_name = dom_node.nodeName
    if close:
      if self.has_child_stuff(dom_node):
        node_list.append(TextNode(u'</%(node_name)s>' % vars()))
    else:
      attr_text = ' '.join(['%s="%s"' % (key, value)
                            for key, value in dom_node.attributes.items()
                            if not key.startswith('py:')])
      # fixme: this is starting to look fugly - hard to maintain and error prone
      if self.has_child_stuff(dom_node):
        if attr_text:
          if attr_ast:
            node_list.append(TextNode(u'<%(node_name)s %(attr_text)s' % vars()))
            node_list.extend(attr_ast)
            node_list.append(TextNode(u'>'))
          else:
            node_list.append(TextNode(u'<%(node_name)s %(attr_text)s>' % vars()))
        else:
          if attr_ast:
            node_list.append(TextNode(u'<%(node_name)s' % vars()))
            node_list.extend(attr_ast)
            node_list.append(TextNode(u'>'))
          else:
            node_list.append(TextNode(u'<%(node_name)s>' % vars()))
      else:
        if attr_text:
          if attr_ast:
            # print "XXX make_tag_node", dom_node.nodeName, attr_ast
            node_list.append(TextNode(u'<%(node_name)s %(attr_text)s' % vars()))
            node_list.extend(attr_ast)
            node_list.append(TextNode(u' />'))
          else:
            node_list.append(TextNode(u'<%(node_name)s %(attr_text)s />' % vars()))
        else:
          if attr_ast:
            node_list.append(TextNode(u'<%(node_name)s' % vars()))
            node_list.extend(attr_ast)
            node_list.append(TextNode(u' />'))
          else:
            node_list.append(TextNode(u'<%(node_name)s />' % vars()))

    omit_tag = getattr(dom_node, 'omit_tag', False)
    omit_tag_ast = getattr(dom_node, 'omit_tag_ast', None)
    if omit_tag:
      if omit_tag_ast:
        if_node = IfNode(omit_tag_ast)
        if_node.extend(node_list)
        return [if_node]
      else:
        return []
      
    return node_list

  def make_attr_node(self, attr):
    node_list = []
    new_attr_name = attr.localName
    attr_ast = spitfire.compiler.util.parse(attr.nodeValue, 'rhs_expression')
    node_list.append(TextNode(u' %(new_attr_name)s="' % vars()))
    # fixme: need to guarantee good output - escape sequences etc
    node_list.append(PlaceholderSubstitutionNode(attr_ast))
    node_list.append(TextNode('"'))
    return node_list

  def handle_define(self, dom_node, attr_name):
    node_list = []
    node_name = dom_node.nodeName
    # print "handle_define", node_name
    # fixme: this is a nasty temp hack, it will generate the correct code
    # for 1 define, but multiple expressions won't work
    ast = spitfire.compiler.util.parse(dom_node.getAttribute(attr_name),
                                      'argument_list')
    dom_node.removeAttribute(attr_name)
    node_list.extend(ast)
    node_list.extend(self.build_ast(dom_node))
    return node_list
  
  
  def handle_content(self, dom_node, attr_name):
    debug("handle_content", dom_node)
    #traceback.print_stack()
    expr_ast = spitfire.compiler.util.parse(
      dom_node.getAttribute(attr_name), 'rhs_expression')
    dom_node.removeAttribute(attr_name)
    setattr(dom_node, 'has_child_stuff', True)
    node_list = []
    debug("handle_content start", dom_node)
    node_list.extend(self.make_tag_node(dom_node))
    node_list.append(PlaceholderSubstitutionNode(expr_ast))
    debug("handle_content end", dom_node)
    node_list.extend(self.make_tag_node(dom_node, close=True))
    debug("handle_content return", dom_node)    
    return node_list

  def handle_omit_tag(self, dom_node, attr_name):
    debug("handle_omit_tag", dom_node)
    node_list = []
    node_name = dom_node.nodeName
    raw_expression = dom_node.getAttribute(attr_name)
    if raw_expression:
      ast = spitfire.compiler.util.parse(raw_expression, 'argument_list')
    else:
      ast = None
    
    dom_node.removeAttribute(attr_name)
    setattr(dom_node, 'omit_tag', True)
    setattr(dom_node, 'omit_tag_ast', ast)
    return node_list

  
  def handle_replace(self, dom_node, attr_name):
    expr_ast = spitfire.compiler.util.parse(
      dom_node.getAttribute(attr_name), 'rhs_expression')
    dom_node.removeAttribute(attr_name)
    return [PlaceholderSubstitutionNode(expr_ast)]


  def has_child_stuff(self, dom_node):
    if getattr(dom_node, 'has_child_stuff', False):
      return True
    has_child_stuff = False
    for attr_name in ('py:content', 'py:replace',):
      if dom_node.hasAttribute(attr_name):
        has_child_stuff = True
        break
    else:
      has_child_stuff = bool(dom_node.childNodes)
    setattr(dom_node, 'has_child_stuff', has_child_stuff)
    return has_child_stuff
  
  def handle_repeat(self, dom_node, attr_name):
    debug("handle_repeat", dom_node)
    expr_pieces = dom_node.getAttribute(attr_name).split()
    dom_node.removeAttribute(attr_name)
    target = expr_pieces[0]
    expr_ast = spitfire.compiler.util.parse(
      ' '.join(expr_pieces[1:]), 'rhs_expression')
    node_list = []
    # hack - assumes python syntax
    fn = ForNode(
      TargetListNode([IdentifierNode("self.repeat['%s']" % target),
                      IdentifierNode(target)]),
      ExpressionListNode([CallFunctionNode(IdentifierNode('enumerate'),
                                           ArgListNode([expr_ast]))]))

    if self.has_child_stuff(dom_node):
      debug("has_child_stuff:", dom_node)
      fn.extend(self.build_ast(dom_node))
      #fn.append(self.make_tag_node(dom_node))
      #for n in dom_node.childNodes:
      #  fn.extend(self.build_ast(n))
    else:
      # print "no children"
      fn.extend(self.build_ast(dom_node))

    if (dom_node.previousSibling and
        dom_node.previousSibling.nodeType == xml.dom.minidom.Node.TEXT_NODE and
        not dom_node.previousSibling.nodeValue.strip()):
      # inject the previous whitespace sibling to keep the output looking ok
      # fixme: a conditional is probably required here - you only want to
      # execute this if it's not the last execution of the loop
      fn.prepend(self.build_ast(dom_node.previousSibling))

      # now remove the previous sibling
      #print "node", dom_node
      #print "parent", dom_node.parentNode
      #print "previous", dom_node.previousSibling, id(dom_node.previousSibling)
      #print "next", dom_node.nextSibling, id(dom_node.nextSibling)
      #dom_node.parentNode.removeChild(dom_node.previousSibling)
      node_list.append(EatPrevious())
        
    node_list.append(fn)
    #fn.extend(self.make_tag_node(dom_node, close=True))
    return node_list


  def handle_condition(self, dom_node, attr_name):
    expr_ast = spitfire.compiler.util.parse(
      dom_node.getAttribute(attr_name), 'rhs_expression')
    node_list = []
    if_node = IfNode(expr_ast)
    node_list.append(if_node)
    if_node.append(self.make_tag_node(dom_node))
    for n in dom_node.childNodes:
      if_node.extend(self.build_ast(n))
    if_node.extend(self.make_tag_node(dom_node, close=True))
    return node_list


  def build_udn_path_ast(self, path):
    pieces = path.split('.')
    node = PlaceholderNode(pieces[0])
    for piece in pieces[1:]:
      node = GetUDNNode(node, piece)
    return node
      
if __name__ == '__main__':
  import sys
  import spitfire.compiler.util
  x2a = XHTML2AST()
  filename = sys.argv[1]
  tnode = x2a.build_template(filename)
  print tnode
  classname = spitfire.compiler.util.filename2classname(filename)
  src = spitfire.compiler.util.compile_ast(tnode, classname)
  print src
  module = spitfire.compiler.util.load_module_from_src(src, '<none>', classname)
  tclass = getattr(module, classname)
  d = {
    'test_x': 'x var',
    'test_y': 'y var',
    'test_z': 'z var',
    'test_number_list': [1, 2, 3, 4, 5],
    'test_object_list': [{'id': 1, 'name': 'o1'},
                         {'id': 2, 'name': 'o2'},
                         {'id': 3, 'name': 'o3'},
                         ],
    'test_dict': {'key1': 1},
    'test_whitespaced_dict': {'key 1': 1},
    'test_range': range,
    'content_type': 'test/spitfire',
    }

  print tclass(search_list=[d]).main()
