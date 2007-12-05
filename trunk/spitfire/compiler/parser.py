# This parser can parse a simple subset of Cheetah's syntax.

from spitfire.compiler.ast import *


from string import *
import re
from yappsrt import *

class SpitfireParserScanner(Scanner):
    patterns = [
        ("'[ \\t]*\\+[ \\t]*'", re.compile('[ \t]*\\+[ \t]*')),
        ("'[ \\t]*\\%[ \\t]*'", re.compile('[ \t]*\\%[ \t]*')),
        ("'[ \\t]*\\/[ \\t]*'", re.compile('[ \t]*\\/[ \t]*')),
        ("'[ \\t]*\\*[ \\t]*'", re.compile('[ \t]*\\*[ \t]*')),
        ("'[ \\t]*\\-[ \\t]*'", re.compile('[ \t]*\\-[ \t]*')),
        ('"[ \\t]*not[ \\t]*"', re.compile('[ \t]*not[ \t]*')),
        ("'[ \\t]*and[ \\t]*'", re.compile('[ \t]*and[ \t]*')),
        ("'[ \\t]*or[ \\t]*'", re.compile('[ \t]*or[ \t]*')),
        ("'[ \\t]*:[ \\t]*'", re.compile('[ \t]*:[ \t]*')),
        ('"\\."', re.compile('\\.')),
        ('"\'"', re.compile("'")),
        ('\'"\'', re.compile('"')),
        ('"[ \\t]*,[ \\t]*"', re.compile('[ \t]*,[ \t]*')),
        ("'#else'", re.compile('#else')),
        ("'#elif'", re.compile('#elif')),
        ("'if'", re.compile('if')),
        ("'for'", re.compile('for')),
        ("'[ \\t]*in[ \\t]*'", re.compile('[ \t]*in[ \t]*')),
        ("'for[ \\t]*'", re.compile('for[ \t]*')),
        ("'def'", re.compile('def')),
        ("'block'", re.compile('block')),
        ("'attr'", re.compile('attr')),
        ("'continue'", re.compile('continue')),
        ("'break'", re.compile('break')),
        ("'slurp'", re.compile('slurp')),
        ("'import'", re.compile('import')),
        ("'from'", re.compile('from')),
        ("'extends'", re.compile('extends')),
        ("'implements'", re.compile('implements')),
        ('DOT', re.compile('\\.')),
        ('NUM', re.compile('[0-9]+')),
        ('ID', re.compile('[A-Za-z_][0-9A-Za-z_]*')),
        ('SINGLE_QUOTE_STR', re.compile("[^']*")),
        ('DOUBLE_QUOTE_STR', re.compile('[^"]*')),
        ('SINGLE_LINE_COMMENT', re.compile('#.*?\n')),
        ('MULTI_LINE_COMMENT', re.compile('\\*[\\W\\w\\S\\s]+\\*#')),
        ('ASSIGN_OPERATOR', re.compile('=')),
        ('COMP_OPERATOR', re.compile('[ \t]*(<|>|==|>=|<=|!=)[ \t]*')),
        ('OPEN_PAREN', re.compile('[ \t]*\\([ \t]*')),
        ('CLOSE_PAREN', re.compile('[ \t]*\\)[ \t]*')),
        ('OPEN_BRACKET', re.compile('[ \t]*\\[[ \t]*')),
        ('CLOSE_BRACKET', re.compile('[ \t]*\\][ \t]*')),
        ('OPEN_BRACE', re.compile('[ \t]*\\{[ \t]*')),
        ('CLOSE_BRACE', re.compile('[ \t]*\\}[ \t]*')),
        ('SPACE', re.compile('[ \t]+')),
        ('CLOSE_DIRECTIVE', re.compile('[ \t]*[\n#]')),
        ('END_DIRECTIVE', re.compile('#end')),
        ('START_DIRECTIVE', re.compile('#')),
        ('START_PLACEHOLDER', re.compile('\\$')),
        ('NEWLINE', re.compile('\n')),
        ('PYTHON_LINE', re.compile('.+')),
        ('TEXT', re.compile('[^#\\$\n]+')),
        ('END', re.compile('$')),
    ]
    def __init__(self, str):
        Scanner.__init__(self,None,[],str)

class SpitfireParser(Parser):
    def goal(self):
        template = TemplateNode()
        while self._peek('END', 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'TEXT') != 'END':
            block = self.block(start=True)
            template.append(block)
        END = self._scan('END')
        return template

    def statement(self):
        _token_ = self._peek("'implements'", "'extends'", "'from'", "'import'", "'slurp'", "'break'", "'continue'", "'attr'")
        if _token_ == "'implements'":
            self._scan("'implements'")
            SPACE = self._scan('SPACE')
            ID = self._scan('ID')
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return ImplementsNode(ID)
        elif _token_ == "'extends'":
            self._scan("'extends'")
            SPACE = self._scan('SPACE')
            modulename = self.modulename()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return ExtendsNode(modulename)
        elif _token_ == "'from'":
            self._scan("'from'")
            SPACE = self._scan('SPACE')
            modulename = self.modulename()
            SPACE = self._scan('SPACE')
            self._scan("'import'")
            SPACE = self._scan('SPACE')
            identifier = self.identifier()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return FromNode(modulename, identifier)
        elif _token_ == "'import'":
            self._scan("'import'")
            SPACE = self._scan('SPACE')
            modulename = self.modulename()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return ImportNode(modulename)
        elif _token_ == "'slurp'":
            self._scan("'slurp'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return CommentNode('slurp')
        elif _token_ == "'break'":
            self._scan("'break'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return BreakNode()
        elif _token_ == "'continue'":
            self._scan("'continue'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return ContinueNode()
        else:# == "'attr'"
            self._scan("'attr'")
            SPACE = self._scan('SPACE')
            placeholder = self.placeholder()
            SPACE = self._scan('SPACE')
            ASSIGN_OPERATOR = self._scan('ASSIGN_OPERATOR')
            SPACE = self._scan('SPACE')
            literal = self.literal()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            return AttributeNode(placeholder.name, literal)

    def modulename(self):
        identifier = self.identifier()
        _module_name_list = [identifier]
        while self._peek('DOT', 'CLOSE_DIRECTIVE', 'SPACE') == 'DOT':
            DOT = self._scan('DOT')
            identifier = self.identifier()
            _module_name_list.append(identifier)
        return _module_name_list

    def directive(self):
        START_DIRECTIVE = self._scan('START_DIRECTIVE')
        _node_list = NodeList()
        _token_ = self._peek('SINGLE_LINE_COMMENT', 'MULTI_LINE_COMMENT', "'block'", "'def'", "'for[ \\t]*'", "'if'", "'implements'", "'extends'", "'from'", "'import'", "'slurp'", "'break'", "'continue'", "'attr'", 'END', 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'")
        if _token_ == 'SINGLE_LINE_COMMENT':
            SINGLE_LINE_COMMENT = self._scan('SINGLE_LINE_COMMENT')
            _node_list.append(CommentNode(START_DIRECTIVE + SINGLE_LINE_COMMENT))
        elif _token_ == 'MULTI_LINE_COMMENT':
            MULTI_LINE_COMMENT = self._scan('MULTI_LINE_COMMENT')
            _node_list.append(CommentNode(START_DIRECTIVE +MULTI_LINE_COMMENT))
        elif _token_ == "'block'":
            self._scan("'block'")
            SPACE = self._scan('SPACE')
            ID = self._scan('ID')
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _block = BlockNode(ID)
            start = CLOSE_DIRECTIVE.endswith('\n')
            while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', 'TEXT') != 'END_DIRECTIVE':
                block = self.block(start)
                _block.append(block)
            make_optional(_block.child_nodes)
            END_DIRECTIVE = self._scan('END_DIRECTIVE')
            SPACE = self._scan('SPACE')
            self._scan("'block'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _node_list.append(_block)
        elif _token_ == "'def'":
            self._scan("'def'")
            SPACE = self._scan('SPACE')
            ID = self._scan('ID')
            _def = DefNode(ID)
            if self._peek('OPEN_PAREN', 'CLOSE_DIRECTIVE') == 'OPEN_PAREN':
                OPEN_PAREN = self._scan('OPEN_PAREN')
                if self._peek('CLOSE_PAREN', 'START_PLACEHOLDER') == 'START_PLACEHOLDER':
                    parameter_list = self.parameter_list()
                    _def.parameter_list = parameter_list
                CLOSE_PAREN = self._scan('CLOSE_PAREN')
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            start = CLOSE_DIRECTIVE.endswith('\n')
            while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', 'TEXT') != 'END_DIRECTIVE':
                block = self.block(start)
                _def.append(block)
            make_optional(_def.child_nodes)
            END_DIRECTIVE = self._scan('END_DIRECTIVE')
            SPACE = self._scan('SPACE')
            self._scan("'def'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _node_list.append(_def)
        elif _token_ == "'for[ \\t]*'":
            self._scan("'for[ \\t]*'")
            target_list = self.target_list()
            self._scan("'[ \\t]*in[ \\t]*'")
            expression_list = self.expression_list()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _for_loop = ForNode(target_list, expression_list)
            start = CLOSE_DIRECTIVE.endswith('\n')
            while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', 'TEXT') != 'END_DIRECTIVE':
                block = self.block(start)
                _for_loop.append(block)
            make_optional(_for_loop.child_nodes)
            END_DIRECTIVE = self._scan('END_DIRECTIVE')
            SPACE = self._scan('SPACE')
            self._scan("'for'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _node_list.append(_for_loop)
        elif _token_ == "'if'":
            self._scan("'if'")
            SPACE = self._scan('SPACE')
            expression = self.expression()
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _if_node = IfNode(expression)
            _last_condition_node = _if_node
            start = CLOSE_DIRECTIVE.endswith('\n')
            while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', "'#elif'", 'TEXT', "'#else'", 'END_DIRECTIVE') not in ["'#elif'", "'#else'", 'END_DIRECTIVE']:
                block = self.block(start)
                _if_node.append(block)
            make_optional(_if_node.child_nodes)
            while self._peek("'#elif'", 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', "'#else'", 'TEXT', 'END_DIRECTIVE') == "'#elif'":
                self._scan("'#elif'")
                SPACE = self._scan('SPACE')
                expression = self.expression()
                CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
                _elif_node = IfNode(expression)
                _if_node.else_.append(_elif_node)
                _last_condition_node = _elif_node
                start = CLOSE_DIRECTIVE.endswith('\n')
                while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'TEXT', "'#elif'", "'#else'", 'END_DIRECTIVE') not in ["'#elif'", "'#else'", 'END_DIRECTIVE']:
                    block = self.block(start)
                    _elif_node.append(block)
            make_optional(_last_condition_node.child_nodes)
            if self._peek("'#else'", 'END_DIRECTIVE') == "'#else'":
                self._scan("'#else'")
                CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
                start = CLOSE_DIRECTIVE.endswith('\n')
                while self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'TEXT', 'END_DIRECTIVE') != 'END_DIRECTIVE':
                    block = self.block(start)
                    _last_condition_node.else_.append(block)
                make_optional(_last_condition_node.else_)
            END_DIRECTIVE = self._scan('END_DIRECTIVE')
            SPACE = self._scan('SPACE')
            self._scan("'if'")
            CLOSE_DIRECTIVE = self._scan('CLOSE_DIRECTIVE')
            _node_list.append(_if_node)
        elif _token_ not in ['END', 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'"]:
            statement = self.statement()
            _node_list.append(statement)
        else:
            _node_list.append(TextNode(START_DIRECTIVE))
        return _node_list

    def block(self, start=False):
        _token_ = self._peek('START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'TEXT')
        if _token_ == 'START_DIRECTIVE':
            directive = self.directive()
            return directive
        elif _token_ == 'TEXT':
            text = self.text()
            return text
        elif _token_ == 'SPACE':
            SPACE = self._scan('SPACE')
            _node_list = NodeList()
            _node_list.append(WhitespaceNode(SPACE))
            if self._peek('START_DIRECTIVE', 'END', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'") == 'START_DIRECTIVE':
                directive = self.directive()
                if start: _node_list[-1] = OptionalWhitespaceNode(SPACE)
                _node_list.append(directive)
            return _node_list
        elif _token_ == 'NEWLINE':
            NEWLINE = self._scan('NEWLINE')
            _node_list = NodeList()
            _node_list.append(NewlineNode(NEWLINE))
            if self._peek('SPACE', 'END', 'START_DIRECTIVE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'") == 'SPACE':
                SPACE = self._scan('SPACE')
                _node_list.append(WhitespaceNode(SPACE))
                if self._peek('START_DIRECTIVE', 'END', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'") == 'START_DIRECTIVE':
                    directive = self.directive()
                    _node_list[-1] = OptionalWhitespaceNode(SPACE)
                    _node_list.append(directive)
            return _node_list
        else:# == 'START_PLACEHOLDER'
            START_PLACEHOLDER = self._scan('START_PLACEHOLDER')
            _primary = TextNode(START_PLACEHOLDER)
            if self._peek('OPEN_BRACE', 'ID', 'END', 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'") in ['OPEN_BRACE', 'ID']:
                _token_ = self._peek('OPEN_BRACE', 'ID')
                if _token_ == 'OPEN_BRACE':
                    OPEN_BRACE = self._scan('OPEN_BRACE')
                    placeholder_in_text = self.placeholder_in_text()
                    CLOSE_BRACE = self._scan('CLOSE_BRACE')
                    _primary = placeholder_in_text
                else:# == 'ID'
                    placeholder_in_text = self.placeholder_in_text()
                    _primary = placeholder_in_text
            if type(_primary) != TextNode: return PlaceholderSubstitutionNode(_primary)
            return _primary

    def text(self):
        TEXT = self._scan('TEXT')
        return TextNode(TEXT)

    def placeholder_in_text(self):
        ID = self._scan('ID')
        _primary = PlaceholderNode(ID)
        while self._peek('DOT', 'OPEN_PAREN', 'OPEN_BRACKET', 'CLOSE_BRACE', 'END', 'START_DIRECTIVE', 'SPACE', 'NEWLINE', 'START_PLACEHOLDER', 'END_DIRECTIVE', "'#elif'", 'TEXT', "'#else'") in ['DOT', 'OPEN_PAREN', 'OPEN_BRACKET']:
            _token_ = self._peek('DOT', 'OPEN_PAREN', 'OPEN_BRACKET')
            if _token_ == 'DOT':
                DOT = self._scan('DOT')
                ID = self._scan('ID')
                _primary = GetUDNNode(_primary, ID)
            elif _token_ == 'OPEN_PAREN':
                OPEN_PAREN = self._scan('OPEN_PAREN')
                _arg_list = None
                if self._peek('CLOSE_PAREN', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") != 'CLOSE_PAREN':
                    argument_list = self.argument_list()
                    _arg_list = argument_list
                CLOSE_PAREN = self._scan('CLOSE_PAREN')
                _primary = CallFunctionNode(_primary, _arg_list)
            else:# == 'OPEN_BRACKET'
                OPEN_BRACKET = self._scan('OPEN_BRACKET')
                expression = self.expression()
                CLOSE_BRACKET = self._scan('CLOSE_BRACKET')
                _primary = SliceNode(_primary, expression)
        return _primary

    def call(self, in_placeholder_context):
        primary = self.primary(in_placeholder_context)
        _primary = primary
        while self._peek('DOT', 'OPEN_PAREN', 'OPEN_BRACKET') == 'DOT':
            DOT = self._scan('DOT')
            ID = self._scan('ID')
            _primary = GetUDNNode(_primary, ID)
        if self._peek('OPEN_PAREN', 'OPEN_BRACKET') == 'OPEN_PAREN':
            OPEN_PAREN = self._scan('OPEN_PAREN')
            _arg_list = None
            if self._peek('CLOSE_PAREN', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") != 'CLOSE_PAREN':
                argument_list = self.argument_list()
                _arg_list = argument_list
            CLOSE_PAREN = self._scan('CLOSE_PAREN')
            _primary = CallFunctionNode(_primary, _arg_list)
        if 1:
            OPEN_BRACKET = self._scan('OPEN_BRACKET')
            expression = self.expression()
            CLOSE_BRACKET = self._scan('CLOSE_BRACKET')
            _primary = SliceNode(_primary, expression)
        return _primary

    def placeholder(self):
        START_PLACEHOLDER = self._scan('START_PLACEHOLDER')
        if self._peek('ID', 'SPACE', 'ASSIGN_OPERATOR', 'DOT', 'OPEN_PAREN', 'OPEN_BRACKET', '"[ \\t]*,[ \\t]*"', "'[ \\t]*in[ \\t]*'", 'CLOSE_PAREN', 'CLOSE_BRACKET', "'[ \\t]*\\*[ \\t]*'", "'[ \\t]*\\/[ \\t]*'", "'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'END', "'[ \\t]*:[ \\t]*'", 'CLOSE_BRACE') == 'ID':
            ID = self._scan('ID')
            return PlaceholderNode(ID)
        return TextNode(START_PLACEHOLDER)

    def target_list(self):
        _target_list = TargetListNode()
        target = self.target()
        _target_list.append(target)
        while self._peek('"[ \\t]*,[ \\t]*"', "'[ \\t]*in[ \\t]*'", 'CLOSE_PAREN', 'CLOSE_BRACKET') == '"[ \\t]*,[ \\t]*"':
            self._scan('"[ \\t]*,[ \\t]*"')
            target = self.target()
            _target_list.append(target)
        return _target_list

    def expression_list(self):
        _expression_list = ExpressionListNode()
        expression = self.expression()
        _expression_list.append(expression)
        while self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_DIRECTIVE') == '"[ \\t]*,[ \\t]*"':
            self._scan('"[ \\t]*,[ \\t]*"')
            expression = self.expression()
            _expression_list.append(expression)
        return _expression_list

    def target(self):
        _token_ = self._peek('START_PLACEHOLDER', 'OPEN_PAREN', 'OPEN_BRACKET')
        if _token_ == 'START_PLACEHOLDER':
            placeholder = self.placeholder()
            return TargetNode(placeholder.name)
        elif _token_ == 'OPEN_PAREN':
            OPEN_PAREN = self._scan('OPEN_PAREN')
            target_list = self.target_list()
            CLOSE_PAREN = self._scan('CLOSE_PAREN')
            return target_list
        else:# == 'OPEN_BRACKET'
            OPEN_BRACKET = self._scan('OPEN_BRACKET')
            target_list = self.target_list()
            CLOSE_BRACKET = self._scan('CLOSE_BRACKET')
            return target_list

    def parameter(self):
        placeholder = self.placeholder()
        _node = ParameterNode(placeholder.name)
        if self._peek('ASSIGN_OPERATOR', '"[ \\t]*,[ \\t]*"', 'CLOSE_PAREN') == 'ASSIGN_OPERATOR':
            ASSIGN_OPERATOR = self._scan('ASSIGN_OPERATOR')
            literal = self.literal()
            _node.default = literal
        return _node

    def parameter_list(self):
        _parameter_list = ParameterListNode()
        parameter = self.parameter()
        _parameter_list.append(parameter)
        while self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_PAREN') == '"[ \\t]*,[ \\t]*"':
            self._scan('"[ \\t]*,[ \\t]*"')
            parameter = self.parameter()
            _parameter_list.append(parameter)
        return _parameter_list

    def stringliteral(self):
        _token_ = self._peek('\'"\'', '"\'"')
        if _token_ == '\'"\'':
            self._scan('\'"\'')
            DOUBLE_QUOTE_STR = self._scan('DOUBLE_QUOTE_STR')
            self._scan('\'"\'')
            return unicode(DOUBLE_QUOTE_STR)
        else:# == '"\'"'
            self._scan('"\'"')
            SINGLE_QUOTE_STR = self._scan('SINGLE_QUOTE_STR')
            self._scan('"\'"')
            return unicode(SINGLE_QUOTE_STR)

    def literal(self):
        _token_ = self._peek('\'"\'', '"\'"', 'NUM')
        if _token_ != 'NUM':
            stringliteral = self.stringliteral()
            return LiteralNode(stringliteral)
        else:# == 'NUM'
            NUM = self._scan('NUM')
            int_part = NUM
            if self._peek('"\\."', 'CLOSE_DIRECTIVE', 'DOT', 'OPEN_PAREN', 'OPEN_BRACKET', '"[ \\t]*,[ \\t]*"', "'[ \\t]*\\*[ \\t]*'", 'CLOSE_PAREN', "'[ \\t]*\\/[ \\t]*'", "'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_BRACKET', 'END', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_BRACE') == '"\\."':
                self._scan('"\\."')
                NUM = self._scan('NUM')
                return LiteralNode(float('%s.%s' % (int_part, NUM)))
            return LiteralNode(int(int_part))

    def identifier(self):
        ID = self._scan('ID')
        return IdentifierNode(ID)

    def primary(self, in_placeholder_context=False):
        _token_ = self._peek('START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE')
        if _token_ == 'START_PLACEHOLDER':
            placeholder = self.placeholder()
            _primary = placeholder
        elif _token_ == 'ID':
            identifier = self.identifier()
            _primary = identifier
            if in_placeholder_context: _primary = PlaceholderNode(_primary.name)
        elif _token_ not in ['OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE']:
            literal = self.literal()
            _primary = literal
        elif _token_ == 'OPEN_BRACKET':
            OPEN_BRACKET = self._scan('OPEN_BRACKET')
            _list_literal = ListLiteralNode()
            if self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_BRACKET', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") not in ['"[ \\t]*,[ \\t]*"', 'CLOSE_BRACKET']:
                expression = self.expression()
                _list_literal.append(expression)
                while self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_BRACKET') == '"[ \\t]*,[ \\t]*"':
                    self._scan('"[ \\t]*,[ \\t]*"')
                    expression = self.expression()
                    _list_literal.append(expression)
            CLOSE_BRACKET = self._scan('CLOSE_BRACKET')
            _primary = _list_literal
        elif _token_ == 'OPEN_PAREN':
            OPEN_PAREN = self._scan('OPEN_PAREN')
            _tuple_literal = TupleLiteralNode()
            if self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_PAREN', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") not in ['"[ \\t]*,[ \\t]*"', 'CLOSE_PAREN']:
                expression = self.expression()
                _tuple_literal.append(expression)
                while self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_PAREN') == '"[ \\t]*,[ \\t]*"':
                    self._scan('"[ \\t]*,[ \\t]*"')
                    expression = self.expression()
                    _tuple_literal.append(expression)
            CLOSE_PAREN = self._scan('CLOSE_PAREN')
            _primary = _tuple_literal
        else:# == 'OPEN_BRACE'
            OPEN_BRACE = self._scan('OPEN_BRACE')
            _dict_literal = DictLiteralNode()
            if self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_BRACE', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") not in ['"[ \\t]*,[ \\t]*"', 'CLOSE_BRACE']:
                expression = self.expression()
                _key = expression
                self._scan("'[ \\t]*:[ \\t]*'")
                expression = self.expression()
                _dict_literal.append((_key, expression))
                while self._peek('"[ \\t]*,[ \\t]*"', 'CLOSE_BRACE') == '"[ \\t]*,[ \\t]*"':
                    self._scan('"[ \\t]*,[ \\t]*"')
                    expression = self.expression()
                    _key = expression
                    self._scan("'[ \\t]*:[ \\t]*'")
                    expression = self.expression()
                    _dict_literal.append((_key, expression))
            CLOSE_BRACE = self._scan('CLOSE_BRACE')
            _primary = _dict_literal
        while self._peek('DOT', 'OPEN_PAREN', 'OPEN_BRACKET', "'[ \\t]*\\*[ \\t]*'", "'[ \\t]*\\/[ \\t]*'", "'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') in ['DOT', 'OPEN_PAREN', 'OPEN_BRACKET']:
            _token_ = self._peek('DOT', 'OPEN_PAREN', 'OPEN_BRACKET')
            if _token_ == 'DOT':
                DOT = self._scan('DOT')
                ID = self._scan('ID')
                _primary = GetUDNNode(_primary, ID)
            elif _token_ == 'OPEN_PAREN':
                OPEN_PAREN = self._scan('OPEN_PAREN')
                _arg_list = None
                if self._peek('CLOSE_PAREN', '"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'") != 'CLOSE_PAREN':
                    argument_list = self.argument_list()
                    _arg_list = argument_list
                CLOSE_PAREN = self._scan('CLOSE_PAREN')
                _primary = CallFunctionNode(_primary, _arg_list)
            else:# == 'OPEN_BRACKET'
                OPEN_BRACKET = self._scan('OPEN_BRACKET')
                expression = self.expression()
                CLOSE_BRACKET = self._scan('CLOSE_BRACKET')
                _primary = SliceNode(_primary, expression)
        return _primary

    def define_list(self):
        argument_list = self.argument_list()
        END = self._scan('END')
        return argument_list

    def rhs_expression(self):
        expression = self.expression()
        END = self._scan('END')
        return expression

    def argument_list(self):
        _pargs, _kargs = [], []
        expression = self.expression()
        _arg = expression
        while self._peek('"[ \\t]*,[ \\t]*"', 'ASSIGN_OPERATOR', 'ID', 'END', 'CLOSE_PAREN') == '"[ \\t]*,[ \\t]*"':
            self._scan('"[ \\t]*,[ \\t]*"')
            _pargs.append(_arg)
            expression = self.expression()
            _arg = expression
        if self._peek('ASSIGN_OPERATOR', 'ID', 'END', 'CLOSE_PAREN') == 'ASSIGN_OPERATOR':
            ASSIGN_OPERATOR = self._scan('ASSIGN_OPERATOR')
            if not isinstance(_arg, IdentifierNode): raise SyntaxError(self._scanner.pos, "keyword arg can't be complex expression")
            _karg = ParameterNode(_arg.name)
            _arg = None
            expression = self.expression()
            _karg.default = expression
            _kargs.append(_karg)
            while self._peek('ID', 'END', 'CLOSE_PAREN') == 'ID':
                identifier = self.identifier()
                _karg = ParameterNode(identifier.name)
                ASSIGN_OPERATOR = self._scan('ASSIGN_OPERATOR')
                expression = self.expression()
                _karg.default = expression
                _kargs.append(_karg)
        if _arg: _pargs.append(_arg)
        return ArgListNode(_pargs, _kargs)

    def keyword_arguments(self):
        keyword_item = self.keyword_item()
        _kargs = [keyword_item]
        return _kargs

    def keyword_item(self):
        expression = self.expression()
        _keyword = expression
        ASSIGN_OPERATOR = self._scan('ASSIGN_OPERATOR')
        raise 'crap'
        expression = self.expression()
        return (_keyword, expression)

    def expression(self):
        or_test = self.or_test()
        return or_test

    def or_test(self):
        and_test = self.and_test()
        _test = and_test
        while self._peek("'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*or[ \\t]*'":
            self._scan("'[ \\t]*or[ \\t]*'")
            and_test = self.and_test()
            _test = BinOpExpressionNode('or', _test, and_test)
        return _test

    def and_test(self):
        not_test = self.not_test()
        _test = not_test
        while self._peek("'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*and[ \\t]*'":
            self._scan("'[ \\t]*and[ \\t]*'")
            not_test = self.not_test()
            _test = BinOpExpressionNode('and', _test, not_test)
        return _test

    def not_test(self):
        _token_ = self._peek('"[ \\t]*not[ \\t]*"', 'START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'")
        if _token_ != '"[ \\t]*not[ \\t]*"':
            comparison = self.comparison()
            return comparison
        else:# == '"[ \\t]*not[ \\t]*"'
            self._scan('"[ \\t]*not[ \\t]*"')
            not_test = self.not_test()
            return UnaryOpNode('not', not_test)

    def u_expr(self):
        _token_ = self._peek('START_PLACEHOLDER', 'ID', '\'"\'', '"\'"', 'NUM', 'OPEN_BRACKET', 'OPEN_PAREN', 'OPEN_BRACE', "'[ \\t]*\\-[ \\t]*'")
        if _token_ != "'[ \\t]*\\-[ \\t]*'":
            primary = self.primary()
            return primary
        else:# == "'[ \\t]*\\-[ \\t]*'"
            self._scan("'[ \\t]*\\-[ \\t]*'")
            u_expr = self.u_expr()
            return UnaryOpNode('-', u_expr)

    def m_expr(self):
        u_expr = self.u_expr()
        _expr = u_expr
        while self._peek("'[ \\t]*\\*[ \\t]*'", "'[ \\t]*\\/[ \\t]*'", "'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*\\*[ \\t]*'":
            self._scan("'[ \\t]*\\*[ \\t]*'")
            u_expr = self.u_expr()
            _expr = BinOpExpressionNode('*', _expr, u_expr)
        while self._peek("'[ \\t]*\\/[ \\t]*'", "'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*\\/[ \\t]*'":
            self._scan("'[ \\t]*\\/[ \\t]*'")
            u_expr = self.u_expr()
            _expr = BinOpExpressionNode('\\', _expr, u_expr)
        while self._peek("'[ \\t]*\\%[ \\t]*'", "'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*\\%[ \\t]*'":
            self._scan("'[ \\t]*\\%[ \\t]*'")
            u_expr = self.u_expr()
            _expr = BinOpExpressionNode('%', _expr, u_expr)
        return _expr

    def a_expr(self):
        m_expr = self.m_expr()
        _expr = m_expr
        while self._peek("'[ \\t]*\\+[ \\t]*'", "'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*\\+[ \\t]*'":
            self._scan("'[ \\t]*\\+[ \\t]*'")
            m_expr = self.m_expr()
            _expr = BinOpExpressionNode('+', _expr, m_expr)
        while self._peek("'[ \\t]*\\-[ \\t]*'", 'COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == "'[ \\t]*\\-[ \\t]*'":
            self._scan("'[ \\t]*\\-[ \\t]*'")
            m_expr = self.m_expr()
            _expr = BinOpExpressionNode('-', _expr, m_expr)
        return _expr

    def comparison(self):
        a_expr = self.a_expr()
        _left_side = a_expr
        while self._peek('COMP_OPERATOR', "'[ \\t]*and[ \\t]*'", "'[ \\t]*or[ \\t]*'", 'CLOSE_DIRECTIVE', 'CLOSE_BRACKET', 'END', '"[ \\t]*,[ \\t]*"', "'[ \\t]*:[ \\t]*'", 'ASSIGN_OPERATOR', 'ID', 'CLOSE_PAREN', 'CLOSE_BRACE') == 'COMP_OPERATOR':
            COMP_OPERATOR = self._scan('COMP_OPERATOR')
            a_expr = self.a_expr()
            _left_side = BinOpExpressionNode(COMP_OPERATOR.strip(), _left_side, a_expr)
        return _left_side


def parse(rule, text):
    P = SpitfireParser(SpitfireParserScanner(text))
    return wrap_error_reporter(P, rule)

if __name__ == '__main__':
    from sys import argv, stdin
    if len(argv) >= 2:
        if len(argv) >= 3:
            f = open(argv[2],'r')
        else:
            f = stdin
        print parse(argv[1], f.read())
    else: print 'Args:  <rule> [<filename>]'
