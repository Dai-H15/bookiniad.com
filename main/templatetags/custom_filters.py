from django import template

register = template.Library()


@register.filter
def split(value, arg):
    """文字列を指定の文字で分割する"""
    if value:
        return value.split(arg)
    return []


@register.filter
def strip(value):
    """文字列の前後の空白を除去する"""
    if value:
        return value.strip()
    return value


@register.filter
def make_list(value):
    """文字列を文字のリストに変換する"""
    return list(str(value))
