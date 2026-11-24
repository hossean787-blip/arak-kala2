from django import template
from django.core.files.storage import default_storage

register = template.Library()

@register.filter
def media_url(name):
    return default_storage.url(name)
