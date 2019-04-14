import typing
from functools import partial

from dataclasses import dataclass
from graphql import (
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLObjectType,
)
from graphql.utilities.schema_printer import print_type

from .constants import IS_STRAWBERRY_FIELD, IS_STRAWBERRY_INPUT
from .type_converter import REGISTRY, get_graphql_type_for_annotation
from .utils.str_converters import to_camel_case


def _get_resolver(cls, field_name):
    def _resolver(obj, info):
        # TODO: can we make this nicer?
        # does it work in all the cases?

        field_resolver = getattr(cls(**(obj.__dict__ if obj else {})), field_name)

        if getattr(field_resolver, IS_STRAWBERRY_FIELD, False):
            return field_resolver(obj, info)

        return field_resolver

    return _resolver


def _convert_annotations_fields(cls, *, is_input=False):
    FieldClass = GraphQLInputField if is_input else GraphQLField
    annotations = typing.get_type_hints(cls, None, REGISTRY)

    fields = {}

    for key, annotation in annotations.items():
        field_name = to_camel_case(key)
        class_field = getattr(cls, key, None)

        description = getattr(class_field, "description", None)

        fields[field_name] = FieldClass(
            get_graphql_type_for_annotation(annotation, key),
            description=description,
            **({} if is_input else {"resolve": _get_resolver(cls, key)})
        )

    return fields


def type(cls, *, is_input=False):
    def wrap():
        name = cls.__name__
        REGISTRY[name] = cls

        def repr_(self):
            return print_type(self.field)

        setattr(cls, "__repr__", repr_)

        def _get_fields():
            fields = _convert_annotations_fields(cls, is_input=is_input)

            fields.update(
                {
                    to_camel_case(key): value.field
                    for key, value in cls.__dict__.items()
                    if getattr(value, IS_STRAWBERRY_FIELD, False)
                }
            )

            return fields

        if is_input:
            cls.field = GraphQLInputObjectType(name, lambda: _get_fields())
            setattr(cls, IS_STRAWBERRY_INPUT, True)
        else:
            cls.field = GraphQLObjectType(name, lambda: _get_fields())

        return dataclass(cls, repr=False)

    return wrap()


input = partial(type, is_input=True)
