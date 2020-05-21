
from pygments.lexers import Python3Lexer
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String


def is_comment(token):
    return token in Comment


def is_decorator(token):
    return token in Name.Decorator


def is_function(token):
    return token in Name.Function


def is_builtin(token):
    return token in Name.Builtin


def is_classname(token):
    return token in Name.Class


def is_keyword(token):
    return token in Keyword


def is_number(token):
    return token in Number


def is_operator(token):
    return token in Operator


def is_punctuation(token):
    return token in Punctuation


def is_string(token):
    return token in String


tokenizer_map = {
    "keyword": is_keyword,
    "builtin": is_builtin,
    "class-name": is_classname,
    "punctuation": is_punctuation,
    "decorator": is_decorator,
    "function": is_function,
    "operator": is_operator,
    "comment": is_comment,
    "string": is_string,
    "number": is_number,
}


def format_code(code):
    pp = Python3Lexer()
    tokens = pp.get_tokens(code)
    formatted = ""
    for token, string in tokens:
        updated = False
        for span_class, checker in tokenizer_map.items():
            if checker(token):
                formatted += f'<span class="token {span_class}">{string}</span>'
                updated = True
                break
        if not updated:
            formatted += string
    return formatted
