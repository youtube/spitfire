# This parser can parse a simple subset of Cheetah's syntax.

from spitfire.compiler.ast import *

%%

parser SpitfireParser:
  token DOT: '\.'
  token NUM:   '[0-9]+'
  token ID:    '[A-Za-z_][0-9A-Za-z_]*'
  #token STR:   r'"([^\\"]+|\\.)*"'
  token SINGLE_QUOTE_STR: "[^']*"
  token DOUBLE_QUOTE_STR: '[^"]*'

  token SINGLE_LINE_COMMENT: '#.*?\n'
  token MULTI_LINE_COMMENT: '\*[\W\w\S\s]+\*#'
  token ASSIGN_OPERATOR: '='
  token COMP_OPERATOR: '[ \t]*(<|>|==|>=|<=|!=)[ \t]*'
  token OPEN_PAREN: '[ \t]*\([ \t]*'
  token CLOSE_PAREN: '[ \t]*\)[ \t]*'
  token OPEN_BRACKET: '[ \t]*\[[ \t]*'
  token CLOSE_BRACKET: '[ \t]*\][ \t]*'
  token OPEN_BRACE: '[ \t]*\{[ \t]*'
  token CLOSE_BRACE: '[ \t]*\}[ \t]*'

  token SPACE: '[ \t]+'
  token CLOSE_DIRECTIVE: '[ \t]*[\n#]'
  token END_DIRECTIVE: '#end'
  token START_DIRECTIVE: '#'
  token START_PLACEHOLDER: '\$'
  token NEWLINE: '\n'
  token PYTHON_LINE: '.+'
  token TEXT: '[^#\$\n]+'
  token END:   '$'

  rule goal:
    {{ template = TemplateNode() }}
    ( block<<start=True>> {{ template.append(block) }} ) *
    END {{ return template }}


  rule statement:
        'implements' SPACE ID CLOSE_DIRECTIVE {{ return ImplementsNode(ID) }}
        |
        'extends' SPACE modulename CLOSE_DIRECTIVE {{ return ExtendsNode(modulename) }}
        |
        'from' SPACE modulename SPACE 'import' SPACE identifier CLOSE_DIRECTIVE {{ return FromNode(modulename, identifier) }}
        |
        'import' SPACE modulename CLOSE_DIRECTIVE {{ return ImportNode(modulename) }}
        |
        'slurp' CLOSE_DIRECTIVE {{ return CommentNode('slurp') }}
        |
        'break' CLOSE_DIRECTIVE {{ return BreakNode() }}
        |
        'continue' CLOSE_DIRECTIVE {{ return ContinueNode() }}
        |
        'attr' SPACE placeholder SPACE ASSIGN_OPERATOR SPACE literal CLOSE_DIRECTIVE
        {{ return AttributeNode(placeholder.name, literal) }}
        
  rule modulename:
    identifier {{ _module_name_list = [identifier] }}
    ( DOT identifier {{ _module_name_list.append(identifier) }} ) *
    {{ return _module_name_list }}

  rule directive:
    START_DIRECTIVE
    {{ _node_list = NodeList() }}
      (
        SINGLE_LINE_COMMENT {{ _node_list.append(CommentNode(START_DIRECTIVE + SINGLE_LINE_COMMENT)) }}
        |
        MULTI_LINE_COMMENT {{ _node_list.append(CommentNode(START_DIRECTIVE +MULTI_LINE_COMMENT)) }}
        |
        'block' SPACE ID CLOSE_DIRECTIVE {{ _block = BlockNode(ID) }}
        {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
        ( block<<start>> {{ _block.append(block) }} ) *
        {{ make_optional(_block.child_nodes) }}
        END_DIRECTIVE SPACE 'block' CLOSE_DIRECTIVE {{ _node_list.append(_block) }}
        |
        'def' SPACE ID {{ _def = DefNode(ID) }}
        [ OPEN_PAREN
          [ parameter_list {{ _def.parameter_list = parameter_list }} ]
          CLOSE_PAREN ]
        CLOSE_DIRECTIVE
        {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
        ( block<<start>> {{ _def.append(block) }} ) *
        {{ make_optional(_def.child_nodes) }}
        END_DIRECTIVE SPACE 'def' CLOSE_DIRECTIVE {{ _node_list.append(_def) }}
        |
        'for[ \t]*' target_list '[ \t]*in[ \t]*' expression_list CLOSE_DIRECTIVE
        {{ _for_loop = ForNode(target_list, expression_list) }}
        {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
        ( block<<start>> {{ _for_loop.append(block) }} ) *
        {{ make_optional(_for_loop.child_nodes) }}
        END_DIRECTIVE SPACE 'for' CLOSE_DIRECTIVE {{ _node_list.append(_for_loop) }}
        |
        'if' SPACE expression CLOSE_DIRECTIVE {{ _if_node = IfNode(expression) }}
        {{ _last_condition_node = _if_node }}
        {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
        ( block<<start>> {{ _if_node.append(block) }} ) *
        {{ make_optional(_if_node.child_nodes) }}
        (
          '#elif' SPACE expression CLOSE_DIRECTIVE {{ _elif_node = IfNode(expression) }}
          {{ _if_node.else_.append(_elif_node) }}
          {{ _last_condition_node = _elif_node }}
          {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
          ( block<<start>> {{ _elif_node.append(block) }} ) *
        ) *
        {{ make_optional(_last_condition_node.child_nodes) }}
        [ '#else' CLOSE_DIRECTIVE
          {{ start = CLOSE_DIRECTIVE.endswith('\n') }}
          ( block<<start>> {{ _last_condition_node.else_.append(block) }} ) *
          {{ make_optional(_last_condition_node.else_) }}
        ]
        END_DIRECTIVE SPACE 'if' CLOSE_DIRECTIVE {{ _node_list.append(_if_node) }}
        |
        statement {{ _node_list.append(statement) }}
        |
        {{ _node_list.append(TextNode(START_DIRECTIVE)) }}
      )
    {{ return _node_list }}


  # NOTE: if we are at the start of a line, we mark the initial whitespace as
  # optional. this is sort of a hack - but i can't quite figure out the right
  # way to describe this syntax
  rule block<<start=False>>:
    directive {{ return directive }}
    |
    text {{ return text }}
    |
    SPACE {{ _node_list = NodeList() }}
    {{ _node_list.append(WhitespaceNode(SPACE)) }}
    [ directive {{ if start: _node_list[-1] = OptionalWhitespaceNode(SPACE) }}
      {{ _node_list.append(directive) }} ]
    {{ return _node_list }}
    |
    NEWLINE {{ _node_list = NodeList() }}
    {{ _node_list.append(NewlineNode(NEWLINE)) }}
    [
      SPACE {{ _node_list.append(WhitespaceNode(SPACE)) }}
      [
        directive {{ _node_list[-1] = OptionalWhitespaceNode(SPACE) }}
        {{ _node_list.append(directive) }}
        ]
    ]
    {{ return _node_list }}
    |
    START_PLACEHOLDER {{ _primary = TextNode(START_PLACEHOLDER) }}
    [
      (
        OPEN_BRACE  placeholder_in_text CLOSE_BRACE {{ _primary = placeholder_in_text }}
        |
        placeholder_in_text {{ _primary = placeholder_in_text }}
      )
    ]
    {{ if type(_primary) != TextNode: return PlaceholderSubstitutionNode(_primary) }}
    {{ return _primary }}
    
  rule text:
    TEXT {{ return TextNode(TEXT) }}

  rule placeholder_in_text:
    ID {{ _primary = PlaceholderNode(ID) }}
    (
        DOT ID {{ _primary = GetUDNNode(_primary, ID) }}
        |
        OPEN_PAREN {{ _arg_list = None }}
        [ argument_list {{ _arg_list = argument_list }} ]
        CLOSE_PAREN {{ _primary = CallFunctionNode(_primary, _arg_list) }}
        |
        OPEN_BRACKET expression CLOSE_BRACKET {{ _primary = SliceNode(_primary, expression) }}
        ) *
    {{ return _primary }}

  rule call<<in_placeholder_context>>:
    # identifier {{ _placeholder = PlaceholderNode(identifier) }}
    primary<<in_placeholder_context>> {{ _primary = primary }}
      ( DOT ID {{ _primary = GetUDNNode(_primary, ID) }} ) *
      [
        OPEN_PAREN {{ _arg_list = None }}
        [ argument_list {{ _arg_list = argument_list }} ]
        CLOSE_PAREN {{ _primary = CallFunctionNode(_primary, _arg_list) }}
      ]
      [
        OPEN_BRACKET expression CLOSE_BRACKET {{ _primary = SliceNode(_primary, expression) }}
      ]
    {{ return _primary }}


  rule placeholder:
    START_PLACEHOLDER
    [ ID {{ return PlaceholderNode(ID) }} ]
    {{ return TextNode(START_PLACEHOLDER) }}


  rule target_list:
    {{ _target_list = TargetListNode() }}
    target {{ _target_list.append(target) }}
    ("[ \t]*,[ \t]*" target {{ _target_list.append(target) }} )*
    # this optional comma cause a SPACE scan in the parse function
    #[","]
    {{ return _target_list }}

  rule expression_list:
    {{ _expression_list = ExpressionListNode() }}
    expression {{ _expression_list.append(expression) }}
    ("[ \t]*,[ \t]*" expression {{ _expression_list.append(expression) }} )*
    # this optional comma cause a SPACE scan in the parse function
    #[","]
    {{ return _expression_list }}

#    expression {{ _expression_list = [expression] }}
#    ("," expression {{ _expression_list.append(expression) }} )* [","] 

  rule target:
    placeholder {{ return TargetNode(placeholder.name) }}
    |
    OPEN_PAREN target_list CLOSE_PAREN {{ return target_list }}
    |
    OPEN_BRACKET target_list CLOSE_BRACKET {{ return target_list }}

   rule parameter:
     placeholder {{ _node = ParameterNode(placeholder.name) }}
     [ ASSIGN_OPERATOR literal {{ _node.default = literal }} ]
     {{ return _node }}

   rule parameter_list:
     {{ _parameter_list = ParameterListNode() }}
     parameter {{ _parameter_list.append(parameter) }}
     ("[ \t]*,[ \t]*" parameter {{ _parameter_list.append(parameter) }} ) *
     {{ return _parameter_list }}
     

  rule stringliteral:
    '"' DOUBLE_QUOTE_STR '"' {{ return unicode(DOUBLE_QUOTE_STR) }}
    |
    "'" SINGLE_QUOTE_STR "'" {{ return unicode(SINGLE_QUOTE_STR) }}

  # had to factor out the floats
  rule literal:
    stringliteral {{ return LiteralNode(stringliteral) }}
    |
    NUM {{ int_part = NUM }}
    [ "\." NUM {{ return LiteralNode(float('%s.%s' % (int_part, NUM))) }} ]
    {{ return LiteralNode(int(int_part)) }}
   
  rule identifier:
    ID {{ return IdentifierNode(ID) }}


  rule primary<<in_placeholder_context=False>>:
    (
      placeholder {{ _primary = placeholder }}
      |
      # atom
      identifier {{ _primary = identifier }}
      {{ if in_placeholder_context: _primary = PlaceholderNode(_primary.name) }}
      |
      literal {{ _primary = literal }}
      |
      OPEN_BRACKET {{ _list_literal = ListLiteralNode() }}
      [
        expression {{ _list_literal.append(expression) }}
        ( "[ \t]*,[ \t]*" expression {{ _list_literal.append(expression) }} ) *
      ]
      CLOSE_BRACKET {{ _primary = _list_literal }}
      |
      OPEN_PAREN {{ _tuple_literal = TupleLiteralNode() }}
      [
        expression {{ _tuple_literal.append(expression) }}
        ( "[ \t]*,[ \t]*" expression {{ _tuple_literal.append(expression) }} ) *
      ]
      CLOSE_PAREN {{ _primary = _tuple_literal }}
      |
      OPEN_BRACE {{ _dict_literal = DictLiteralNode() }}
      [
        expression {{ _key = expression }}
        '[ \t]*:[ \t]*'
        expression {{ _dict_literal.append((_key, expression)) }}
        ( "[ \t]*,[ \t]*" expression {{ _key = expression }}
          '[ \t]*:[ \t]*' expression
          {{ _dict_literal.append((_key, expression)) }}
          ) *
      ]
      CLOSE_BRACE {{ _primary = _dict_literal }}
    )
    (
      # fixme: this chunk here is shared with the main loop for handling
      # placeholder parsing
      DOT ID {{ _primary = GetUDNNode(_primary, ID) }}
      |
      OPEN_PAREN {{ _arg_list = None }}
      [ argument_list {{ _arg_list = argument_list }} ]
      CLOSE_PAREN {{ _primary = CallFunctionNode(_primary, _arg_list) }}
      |
      OPEN_BRACKET expression CLOSE_BRACKET {{ _primary = SliceNode(_primary, expression) }}
    ) *
    {{ return _primary }}

  # extra rules for parsing the attribute language
  rule define_list:
    argument_list END {{ return argument_list }}

  rule rhs_expression:
    expression END {{ return expression }}

  # TODO: need to factor out commonalities of pargs and kargs patterns
  # FIXME: seems like a hack - should these all be ParameterNodes and replace
  # the name arg with a real expression?
  rule argument_list:
    {{ _pargs, _kargs = [], [] }}
    expression {{ _arg = expression }}
    (
    "[ \t]*,[ \t]*" {{ _pargs.append(_arg) }}
    expression {{ _arg = expression }}
    ) *
    [
    ASSIGN_OPERATOR
    {{ if not isinstance(_arg, IdentifierNode): raise SyntaxError(self._scanner.pos, "keyword arg can't be complex expression") }}
    {{ _karg = ParameterNode(_arg.name) }}
    {{ _arg = None }}
    expression {{ _karg.default = expression }}
    {{ _kargs.append(_karg) }}
    (
      identifier {{ _karg = ParameterNode(identifier.name) }}
      ASSIGN_OPERATOR
      expression {{ _karg.default = expression }}
      {{ _kargs.append(_karg) }}
    ) *
    ]
    {{ if _arg: _pargs.append(_arg) }}
    {{ return ArgListNode(_pargs, _kargs) }}

  rule keyword_arguments:
    keyword_item {{ _kargs = [keyword_item] }}
    {{ return _kargs }}

  # fixme: to properly handle this as "identifier=expression" i need to factor
  # out common prefixes in positional/keyword args
  rule keyword_item:
    expression {{ _keyword = expression }}
    ASSIGN_OPERATOR {{ raise 'crap' }}
    expression {{ return (_keyword, expression) }}

  rule expression:
    or_test {{ return or_test }}
    # primary {{ return primary }}

  rule or_test:
    and_test {{ _test = and_test }}
    ( '[ \t]*or[ \t]*' and_test {{ _test = BinOpExpressionNode('or', _test, and_test) }} ) *
    {{ return _test }}

  rule and_test:
    not_test {{ _test = not_test }}
    ( '[ \t]*and[ \t]*' not_test {{ _test = BinOpExpressionNode('and', _test, not_test) }} ) *
    {{ return _test }}
    
  rule not_test:
    comparison {{ return comparison }}
    |
    "[ \t]*not[ \t]*" not_test {{ return UnaryOpNode('not', not_test) }}
    
  rule u_expr:
    primary {{ return primary }}
    |
    '[ \t]*\-[ \t]*' u_expr {{ return UnaryOpNode('-', u_expr) }}


  rule m_expr:
    u_expr {{ _expr = u_expr }}
    ( '[ \t]*\*[ \t]*' u_expr {{ _expr = BinOpExpressionNode('*', _expr, u_expr) }} ) *
    ( '[ \t]*\/[ \t]*' u_expr {{ _expr = BinOpExpressionNode('\\', _expr, u_expr) }} ) *
    ( '[ \t]*\%[ \t]*' u_expr {{ _expr = BinOpExpressionNode('%', _expr, u_expr) }} ) *
    {{ return _expr }}


  rule a_expr:
    m_expr {{ _expr = m_expr }}
    ( '[ \t]*\+[ \t]*' m_expr {{ _expr = BinOpExpressionNode('+', _expr, m_expr) }} ) *
    ( '[ \t]*\-[ \t]*' m_expr {{ _expr = BinOpExpressionNode('-', _expr, m_expr) }} ) *
    {{ return _expr }}


  rule comparison:
    a_expr {{ _left_side = a_expr }}
    ( COMP_OPERATOR a_expr {{ _left_side = BinOpExpressionNode(COMP_OPERATOR.strip(), _left_side, a_expr) }} ) *
    {{ return _left_side }}
