# -*- coding: utf-8 -*-
import rest_framework
import inspect

from rest_framework.compat import apply_markdown
from .constants import INTROSPECTOR_PRIMITIVES


def get_serializer_name(serializer):
    if serializer is None:
        return None
    if rest_framework.VERSION >= '3.0.0':
        from rest_framework.serializers import ListSerializer
        assert serializer != ListSerializer, "uh oh, what now?"
        if isinstance(serializer, ListSerializer):
            serializer = serializer.child

    if hasattr(serializer, 'Meta') and hasattr(serializer.Meta, 'swagger_name') and serializer.Meta.swagger_name:
        return serializer.Meta.swagger_name

    if inspect.isclass(serializer):
        return serializer.__name__

    return serializer.__class__.__name__


def get_view_description(view_cls, html=False, docstring=None):
    if docstring is not None:
        view_cls = type(
            view_cls.__name__ + '_fake',
            (view_cls,),
            {'__doc__': docstring})
    return rest_framework.settings.api_settings \
        .VIEW_DESCRIPTION_FUNCTION(view_cls, html)


def get_default_value(field):
    default_value = getattr(field, 'default', None)
    if rest_framework.VERSION >= '3.0.0':
        from rest_framework.fields import empty
        if default_value == empty:
            default_value = None
    if callable(default_value):
        default_value = default_value()
    return default_value


def extract_base_path(path, base_path):
    """
    extracts the base_path at the begining of the path
    e.g:
        extract_base_path(path="/foo/bar", base_path="/foo") => "/bar"
    """
    if path.startswith(base_path):
        path = path[len(base_path):]
    return path


def do_markdown(docstring):
    # Markdown is optional
    if apply_markdown:
        return apply_markdown(docstring)
    else:
        return docstring.replace("\n\n", "<br/>")


def multi_getattr(obj, attr, default=None):
    """
    Get a named attribute from an object; multi_getattr(x, 'a.b.c.d') is
    equivalent to x.a.b.c.d. When a default argument is given, it is
    returned when any attribute in the chain doesn't exist; without
    it, an exception is raised when a missing attribute is encountered.

    """
    attributes = attr.split(".")
    for i in attributes:
        try:
            obj = getattr(obj, i)
        except AttributeError:
            if default:
                return default
            else:
                raise
    return obj


def normalize_data_format(data_type, data_format, obj):
    """
    sets 'type' on obj
    sets a valid 'format' on obj if appropriate
    uses data_format only if valid
    """
    if data_type == 'array':
        data_format = None

    flatten_primitives = [
        val for sublist in INTROSPECTOR_PRIMITIVES.values()
        for val in sublist
    ]

    if data_format not in flatten_primitives:
        formats = INTROSPECTOR_PRIMITIVES.get(data_type, None)
        if formats:
            data_format = formats[0]
        else:
            data_format = None
    if data_format == data_type:
        data_format = None

    obj['type'] = data_type
    if data_format is None and 'format' in obj:
        del obj['format']
    elif data_format is not None:
        obj['format'] = data_format
