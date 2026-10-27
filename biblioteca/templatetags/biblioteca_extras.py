from django import template

register = template.Library()


@register.filter
def stars(rating):
    """Convierte una nota (1-5, puede ser decimal) en estrellas: 3.6 → ★★★★☆"""
    if not rating:
        return ''
    llenas = min(5, max(0, round(float(rating))))
    return '★' * llenas + '☆' * (5 - llenas)
