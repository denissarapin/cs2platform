from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """
    Позволяет в шаблоне брать элемент словаря по ключу:
    {{ my_dict|get_item:key }}
    """
    if isinstance(d, dict):
        return d.get(key)
    return None
