"""Generates API documentation by introspection."""
from importlib import import_module
from django.contrib.auth.models import AnonymousUser
import rest_framework

from rest_framework import viewsets, mixins
from rest_framework.generics import GenericAPIView

from rest_framework.serializers import BaseSerializer, ListField

from .introspectors import (
    APIViewIntrospector,
    GenericViewIntrospector,
    BaseMethodIntrospector,
    ViewSetIntrospector,
    WrappedAPIViewIntrospector,
    get_data_type,
)
from .compat import OrderedDict
from .utils import extract_base_path, get_serializer_name, get_default_value


class DocumentationGenerator(object):
    # Serializers defined in docstrings
    explicit_serializers = set()

    # Serializers defined in fields
    fields_serializers = set()

    # Response classes defined in docstrings
    explicit_response_types = dict()

    def __init__(self, for_user=None, config=None, request=None, config_name=None):
        self.config = config
        self.config_name = config_name
        self.user = for_user or AnonymousUser()
        self.request = request

    def get_root(self, endpoints_conf):
        self.default_payload_definition_name = self.config.get("default_payload_definition_name", None)
        self.default_payload_definition = self.config.get("default_payload_definition", None)
        if self.default_payload_definition:
            self.explicit_response_types.update({
                self.default_payload_definition_name: self.default_payload_definition
            })
        return {
            'swagger': '2.0',
            'info': self.config.get('info', {
                'contact': '',
            }),
            'basePath': self.config.get("basePath", '').format(
                version=self.request.parser_context['kwargs'].get('version', '')
            ),
            'host': self.config.get('host', ''),
            'schemes': self.config.get('schemes', ''),
            'paths': self.get_paths(endpoints_conf),
            'definitions': self.get_definitions(endpoints_conf),
            'securityDefinitions': self.config.get('securityDefinitions', {}),
            'security': self.config.get('security', []),

        }

    def get_paths(self, endpoints_conf):
        paths_dict = {}
        for endpoint in endpoints_conf:
            # remove the base_path from the begining of the path
            endpoint['path'] = extract_base_path(path=endpoint['path'], base_path=self.config.get('basePath'))
            path_item = self.get_path_item(endpoint)
            if path_item:
                paths_dict[endpoint['path']] = path_item

        paths_dict = OrderedDict(sorted(paths_dict.items()))
        return paths_dict

    def get_path_item(self, api_endpoint):
        introspector = self.get_introspector(api_endpoint)

        path_item = {}

        for operation in self.get_operations(api_endpoint, introspector):
            path_item[operation.pop('method').lower()] = operation
        if not path_item:
            return False

        method_introspectors = self.get_method_introspectors(api_endpoint, introspector)
        # we get the main parameters (common to all operations) from the first view operation
        # only path parameters are commont to all operations
        path_item['parameters'] = self.fill_path_parameters(method_introspectors[0].build_path_parameters())
        return path_item

    def fill_path_parameters(self, path_parameters):
        """
        If configured it will try to import the global parameters definition
        (from the swagger config) and (if found) will merge the gobal parameters
        definitions with the path_parameters.
        This is used for parameters defined in the url path
        """
        if not path_parameters:
            return []

        params_module = self.config.get('global_parametters_docs')
        if not params_module:
            return path_parameters

        params_module = import_module(params_module)

        global_parameters = getattr(params_module, 'GLOBAL_PARAMETERS')

        for parameter in path_parameters:
            global_param = global_parameters.get(parameter['name'])
            if global_param:
                parameter.update(global_param)
        return path_parameters

    def get_method_introspectors(self, api_endpoint, introspector):
        return [method_introspector for method_introspector in introspector if
                isinstance(method_introspector, BaseMethodIntrospector) and
                not method_introspector.get_http_method() == "OPTIONS"]

    def get_operations(self, api_endpoint, introspector):
        """
        Return docs for the allowed methods of an API endpoint
        """
        operations = []

        for method_introspector in self.get_method_introspectors(api_endpoint, introspector):
            doc_parser = method_introspector.get_yaml_parser()
            # check if operation is allowed on the current swagger config name
            operation_config_name = doc_parser.get_param(param_name='swagger_config_name', default=False)
            if operation_config_name and operation_config_name != self.config_name:
                continue

            operation_method = method_introspector.get_http_method()
            operation_security = method_introspector.get_security()

            operation = {
                'method': operation_method,
                'description': method_introspector.get_description(),
                'summary': method_introspector.get_summary(),
                'operationId': method_introspector.get_operation_id(),
                'produces': doc_parser.get_param(param_name='produces', default=self.config.get('produces')),
                'tags': doc_parser.get_param(param_name='tags', default=[]),
                'parameters': self._get_operation_parameters(method_introspector, operation_method)
            }

            if operation_security is not None:
                operation['security'] = operation_security

            if doc_parser.yaml_error is not None:
                operation['notes'] += '<pre>YAMLError:\n {err}</pre>'.format(
                    err=doc_parser.yaml_error)

            response_messages = {}
            # set default response reference
            if self.default_payload_definition:
                response_messages['default'] = {
                    "description": "error payload",
                    "schema": {
                        "$ref": "#/definitions/{}".format(self.default_payload_definition_name)
                    }
                }

            # write the default "success" responses
            success_code, success_body = self._get_operation_success_response(
                doc_parser, method_introspector
            )
            response_messages[success_code] = success_body

            # overwrite default and add more responses from docstrings
            response_messages.update(doc_parser.get_response_messages())

            operation['responses'] = response_messages

            operations.append(operation)

        return operations

    def _get_operation_success_response(self, doc_parser, method_introspector):
        response_serializer = method_introspector.get_response_serializer_class()

        response_serializer_name = get_serializer_name(response_serializer)

        operation_method = method_introspector.get_http_method().lower()

        success_code = "200"

        if operation_method == "delete":
            return ("204", {"description": "Deleted"})

        if operation_method == "post":
            success_code = "201"

        response_object = {
            '$ref': '#/definitions/' + response_serializer_name
        } if response_serializer_name != 'object' else {
            'type': response_serializer_name
        }

        # pagination
        if (doc_parser.force_pagination() or
           (success_code == "200" and method_introspector.get_pagination_class())):
            success_body = {
                'description': 'Successful operation',
                'schema': {
                    'type': 'object',
                    "properties": {
                        'next': {
                            'readOnly': True,
                            'type': 'string',
                            'description': ''
                        },
                        'previous': {
                            'readOnly': True,
                            'type': 'string',
                            'description': ''
                        },
                        'count': {
                            'readOnly': True,
                            'type': 'integer',
                            'description': ''
                        },
                        'results': {
                            'readOnly': True,
                            'type': 'array',
                            'description': '',
                            'items': response_object
                        },
                        'page': {
                            'readOnly': True,
                            'type': 'integer',
                            'description': ''
                        },
                        'size': {
                            'readOnly': True,
                            'type': 'integer',
                            'description': ''
                        }
                    }
                }
            }
            return (success_code, success_body)

        success_body = {
            'description': 'Successful operation',
            'schema': response_object
        }

        return (success_code, success_body)

    def _get_operation_parameters(self, introspector, method):
        """
        :param introspector: method introspector
        :return : if the serializer must be placed in the body, it will build
        the body parameters and add the serializer to the explicit_serializers list
        else it will discover the parameters (from docstring and serializer)
        """
        serializer = introspector.get_request_serializer_class()
        parameters = []
        if (method in ('POST', 'PUT', 'PATCH') and hasattr(serializer, "Meta") and
           hasattr(serializer.Meta, "_in") and serializer.Meta._in == "body"):
            self.explicit_serializers.add(serializer)
            parameters.append(introspector.build_body_parameters())

        parameters.extend(
            introspector.get_yaml_parser().discover_parameters(inspector=introspector)
        )
        return parameters

    def get_introspector(self, api):
        path = api['path']
        pattern = api['pattern']
        callback = api['callback']
        if callback.__module__ == 'rest_framework.decorators':
            return WrappedAPIViewIntrospector(callback, path, pattern, self.user)
        elif issubclass(callback, viewsets.ViewSetMixin):
            patterns = [api['pattern']]
            return ViewSetIntrospector(callback, path, pattern, self.user, patterns=patterns)
        elif issubclass(callback, GenericAPIView) and self._callback_generic_is_implemented(callback):
            return GenericViewIntrospector(callback, path, pattern, self.user)
        else:
            return APIViewIntrospector(callback, path, pattern, self.user)

    def _callback_generic_is_implemented(self, callback):
        """
        An implemented callback is a view that extends from one of the GenericApiView child.
        Because some views might extend directly from GenericAPIView without
        implementing one of the List, Create, Retrieve, etc. mixins
        """
        return (issubclass(callback, mixins.CreateModelMixin) or
                issubclass(callback, mixins.ListModelMixin) or
                issubclass(callback, mixins.RetrieveModelMixin) or
                issubclass(callback, mixins.UpdateModelMixin) or
                issubclass(callback, mixins.DestroyModelMixin))

    def get_definitions(self, endpoints_conf):
        """
        Builds a list of Swagger 'models'. These represent
        DRF serializers and their fields
        """
        serializers = self._get_serializer_set(endpoints_conf)
        serializers.update(self.explicit_serializers)
        serializers.update(
            self._find_field_serializers(serializers)
        )

        models = {}

        for serializer in serializers:
            serializer_name = get_serializer_name(serializer)

            if hasattr(serializer, "Meta") and hasattr(serializer.Meta, "child"):
                child_serializer = serializer.Meta.child
                child_serializer_name = get_serializer_name(child_serializer)
                models[child_serializer_name] = self.get_definition(child_serializer)

            models[serializer_name] = self.get_definition(serializer)

        models.update(self.explicit_response_types)
        models.update(self.fields_serializers)
        return models

    def get_definition(self, serializer):
        """
        :param serializer: Serializer to describe
        :type serializer: serializer instance
        """
        data = self._get_serializer_fields(serializer)
        serializer_type = "object"
        properties = OrderedDict((k, v) for k, v in data['fields'].items()
                                 if k not in data['write_only'])

        if hasattr(serializer, "Meta") and hasattr(serializer.Meta, "child"):
            return {
                'type': 'array',
                'items': {
                    '$ref': '#/definitions/{}'.format(
                        get_serializer_name(serializer.Meta.child)
                    )
                }
            }

        definition = {
            'properties': properties,
            'type': serializer_type
        }
        required_properties = [i for i in properties.keys() if i in data.get("required", [])]
        if required_properties:
            definition['required'] = required_properties

        return definition

    def _get_serializer_set(self, endpoints_conf):
        """
        Returns a set of serializer classes for a provided list
        of APIs
        """
        serializers = set()

        for endpoint in endpoints_conf:
            introspector = self.get_introspector(endpoint)
            for method_introspector in introspector:
                serializer = method_introspector.get_response_serializer_class()
                if serializer is not None:
                    serializers.add(serializer)
                extras = method_introspector.get_extra_serializer_classes()
                for extra in extras:
                    if extra is not None:
                        serializers.add(extra)

        return serializers

    def _find_field_serializers(self, serializers, found_serializers=set()):
        """
        Returns set of serializers discovered from fields
        """
        def get_thing(field, key):
            if rest_framework.VERSION >= '3.0.0':
                from rest_framework.serializers import ListSerializer
                if isinstance(field, ListSerializer):
                    return key(field.child)
            return key(field)

        serializers_set = set()
        for serializer in serializers:
            fields = serializer().get_fields()
            for name, field in fields.items():
                if isinstance(field, BaseSerializer):
                    serializers_set.add(get_thing(field, lambda f: f))
                    if field not in found_serializers:
                        serializers_set.update(
                            self._find_field_serializers(
                                (get_thing(field, lambda f: f.__class__),),
                                serializers_set))

        return serializers_set

    def _get_serializer_fields(self, serializer):
        """
        Returns serializer fields in the Swagger MODEL format
        """
        if serializer is None:
            return

        if hasattr(serializer, '__call__'):
            fields = serializer().get_fields()
        else:
            fields = serializer.get_fields()

        data = OrderedDict({
            'fields': OrderedDict(),
            'required': [],
            'write_only': [],
            'read_only': [],
        })
        for name, field in fields.items():
            if getattr(field, 'write_only', False):
                data['write_only'].append(name)

            if getattr(field, 'read_only', False):
                data['read_only'].append(name)

            if getattr(field, 'required', False):
                data['required'].append(name)

            data_type, data_format = get_data_type(field) or ('string', 'string')

            if data_type == 'hidden':
                continue

            # guess format
            # data_format = 'string'
            # if data_type in BaseMethodIntrospector.PRIMITIVES:
                # data_format = BaseMethodIntrospector.PRIMITIVES.get(data_type)[0]

            description = getattr(field, 'help_text', '')
            if not description or description.strip() == '':
                description = ""
            f = {
                'description': description,
                'type': data_type,
                'format': data_format,
                # 'required': getattr(field, 'required', False),
                'default': get_default_value(field),
                'readOnly': getattr(field, 'read_only', None),
            }

            # Swagger type is a primitive, format is more specific
            if f['type'] == f['format']:
                del f['format']

            # defaultValue of null is not allowed, it is specific to type
            if f['default'] is None:
                del f['default']

            # Min/Max values
            max_value = getattr(field, 'max_value', None)
            min_value = getattr(field, 'min_value', None)
            if max_value is not None and data_type == 'integer':
                f['minimum'] = min_value

            if max_value is not None and data_type == 'integer':
                f['maximum'] = max_value

            # ENUM options
            if data_type in BaseMethodIntrospector.ENUMS:
                if isinstance(field.choices, list):
                    f['enum'] = [k for k, v in field.choices]
                elif isinstance(field.choices, dict):
                    f['enum'] = [k for k, v in field.choices.items()]

            # Support for complex types
            if rest_framework.VERSION < '3.0.0':
                has_many = hasattr(field, 'many') and field.many
            else:
                from rest_framework.serializers import ListSerializer, ManyRelatedField
                has_many = isinstance(field, (ListSerializer, ManyRelatedField))

            if isinstance(field, BaseSerializer) or has_many:
                if hasattr(field, 'is_documented') and not field.is_documented:
                    f['type'] = 'object'
                elif isinstance(field, BaseSerializer):
                    field_serializer = get_serializer_name(field)

                    if getattr(field, 'write_only', False):
                        field_serializer = "Write{}".format(field_serializer)

                    if not has_many:
                        del f['type']
                        f['$ref'] = '#/definitions/' + field_serializer
                else:
                    field_serializer = None
                    data_type = 'string'

                if has_many:
                    f['type'] = 'array'
                    if field_serializer:
                        f['items'] = {'$ref': '#/definitions/' + field_serializer}
                    elif data_type in BaseMethodIntrospector.PRIMITIVES:
                        f['items'] = {'type': data_type}
            elif isinstance(field, ListField):
                f['type'] = 'array'
                if not field.child:
                    f['items'] = {'type': 'string'}
                child_type, child_format = get_data_type(field.child) or ('string', 'string')
                f['items'] = {'type': child_type}
            # memorize discovered field
            data['fields'][name] = f
        return data
