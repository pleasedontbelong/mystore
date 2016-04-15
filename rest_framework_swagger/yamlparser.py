# -*- coding: utf-8 -*-

import yaml
import importlib
from django.utils import six
from django.contrib.admindocs.utils import trim_docstring
from rest_framework.utils import formatting

from .compat import OrderedDict
from .utils import multi_getattr, normalize_data_format, get_serializer_name


class YAMLDocstringParser(object):
    """
    Docstring parser powered by YAML syntax

    This parser allows you override some parts of automatic method inspection
    behaviours which are not always correct.

    See the following documents for more information about YAML and Swagger:
    - https://github.com/wordnik/swagger-core/wiki
    - http://www.yaml.org/spec/1.2/spec.html
    - https://github.com/wordnik/swagger-codegen/wiki/Creating-Swagger-JSON-from-YAML-files

    1. Control over parameters
    ============================================================================
    Define parameters and its properties in docstrings:

        parameters:
            - name: some_param
              description: Foobar long description goes here
              required: true
              type: integer
              in: form
              minimum: 10
              maximum: 100
            - name: other_foo
              in: query
            - name: avatar
              type: file

    It is possible to override parameters discovered by method inspector by
    defining:
        `parameters_strategy` option to either `merge` or `replace`

    To define different strategies for different `in`'s use the
    following syntax:
        parameters_strategy:
            form: replace
            query: merge

    By default strategy is set to `merge`


    Sometimes method inspector produces wrong list of parameters that
    you might not won't to see in SWAGGER form. To handle this situation
    define `ins` that should be omitted
        omit_parameters:
            - form

    2. Control over serializers
    ============================================================================
    Once in a while you are using different serializers inside methods
    but automatic method inspector cannot detect this. For that purpose there
    is two explicit parameters that allows you to discard serializer detected
    by method inspector OR replace it with another one

        serializer: some.package.FooSerializer
        omit_serializer: true

    3. Custom Response Class
    ============================================================================
    If your view is not using serializer at all but instead outputs simple
    data type such as JSON you may define custom response object in method
    signature like follows:

        type:
          name:
            required: true
            type: string
          url:
            required: false
            type: url

    4. Response Messages (Error Codes)
    ============================================================================
    If you'd like to share common response errors that your APIView might throw
    you can define them in docstring using following format:

    responseMessages:
        - code: 401
          message: Not authenticated
        - code: 403
          message: Insufficient rights to call this procedure


    5. Different models for reading and writing operations
    ============================================================================
    Since REST Framework won't output write_only fields in responses as well as
    does not require read_only fields to be provided it is worth to
    automatically register 2 separate models for reading and writing operations.

    Discovered serializer will be registered with `Write` or `Read` prefix.
    Response Class will be automatically adjusted if serializer class was
    detected by method inspector.

    You can also refer to this models in your parameters:

    parameters:
        - name: CigarSerializer
          type: WriteCigarSerializer
          in: body


    SAMPLE DOCSTRING:
    ============================================================================

    ---
    # API Docs
    # Note: YAML always starts with `---`

    type:
      name:
        required: true
        type: string
      url:
        required: false
        type: url
      created_at:
        required: true
        type: string
        format: date-time

    serializer: .serializers.FooSerializer
    omit_serializer: false

    parameters_strategy: merge
    omit_parameters:
        - path
    parameters:
        - name: name
          description: Foobar long description goes here
          required: true
          type: string
          in: form
        - name: other_foo
          in: query
        - name: other_bar
          in: query
        - name: avatar
          type: file

    responseMessages:
        - code: 401
          message: Not authenticated
    """
    PARAM_TYPES = ['header', 'path', 'formData', 'body', 'query']
    yaml_error = None

    def __init__(self, method_introspector):
        self.method_introspector = method_introspector
        self.object = self.load_obj_from_docstring(
            docstring=self.method_introspector.get_docs())
        if self.object is None:
            self.object = {}

    def load_obj_from_docstring(self, docstring):
        """Loads YAML from docstring"""
        split_lines = trim_docstring(docstring).split('\n')

        # Cut YAML from rest of docstring
        for index, line in enumerate(split_lines):
            line = line.strip()
            if line.startswith('---'):
                cut_from = index
                break
        else:
            return None

        yaml_string = "\n".join(split_lines[cut_from:])
        yaml_string = formatting.dedent(yaml_string)
        try:
            return yaml.load(yaml_string)
        except yaml.YAMLError as e:
            self.yaml_error = e
            return None

    def _load_class(self, cls_path, callback):
        """
        Dynamically load a class from a string
        """
        if not cls_path or not callback or not hasattr(callback, '__module__'):
            return None

        package = None

        if '.' not in cls_path:
            # within current module/file
            class_name = cls_path
            module_path = self.method_introspector.get_module()
        else:
            # relative or fully qualified path import
            class_name = cls_path.split('.')[-1]
            module_path = ".".join(cls_path.split('.')[:-1])

            if cls_path.startswith('.'):
                # relative lookup against current package
                # ..serializers.FooSerializer
                package = self.method_introspector.get_module()

        class_obj = None
        # Try to perform local or relative/fq import
        try:
            module = importlib.import_module(module_path, package=package)
            class_obj = getattr(module, class_name, None)
        except ImportError:
            pass

        # Class was not found, maybe it was imported to callback module?
        # from app.serializers import submodule
        # serializer: submodule.FooSerializer
        if class_obj is None:
            try:
                module = importlib.import_module(
                    self.method_introspector.get_module())
                class_obj = multi_getattr(module, cls_path, None)
            except (ImportError, AttributeError):
                raise Exception("Could not find %s, looked in %s" % (cls_path, module))

        return class_obj

    def get_serializer_class(self, callback):
        """
        Retrieves serializer class from YAML object
        """
        serializer = self.object.get('serializer', None)
        try:
            return self._load_class(serializer, callback)
        except (ImportError, ValueError):
            pass
        return None

    def get_extra_serializer_classes(self, callback):
        """
        Retrieves serializer classes from pytype YAML objects
        """
        parameters = self.object.get('parameters', [])
        serializers = []
        for parameter in parameters:
            serializer = parameter.get('pytype', None)
            if serializer is not None:
                try:
                    serializer = self._load_class(serializer, callback)
                    serializers.append(serializer)
                except (ImportError, ValueError):
                    pass
        return serializers

    def get_yaml_request_serializer_class(self, callback):
        """
        Retrieves request serializer class from YAML object
        """
        serializer = self.object.get('request_serializer', None)
        try:
            return self._load_class(serializer, callback)
        except (ImportError, ValueError):
            pass
        return None

    def get_yaml_response_serializer_class(self, callback):
        """
        Retrieves response serializer class from YAML object
        """
        serializer = self.object.get('response_serializer', None)
        try:
            return self._load_class(serializer, callback)
        except (ImportError, ValueError):
            pass
        return None

    def get_yaml_security_definition(self, callback):
        """
        Retrieves the security reference of the operation
        """
        security = self.object.get('security', None)
        # if "security" is not defined on the yaml docstring
        if not security:
            return None
        # if security is defined as "public" declare an empty security
        if security == 'public':
            return []
        # finally return whathever it was defined on the docstring
        return security

    def get_response_type(self):
        """
        Docstring may define custom response class
        """
        return self.object.get('type', None)

    def get_response_messages(self):
        """
        Retrieves response error codes from YAML object
        """
        messages = {}
        response_messages = self.object.get('responseMessages', [])
        for message in response_messages:
            data = {
                'description': message.get('description', '')
            }
            schema = message.get('schema', None)
            if schema:
                data['schema'] = schema
            messages[str(message.get('code'))] = data
        return messages

    def get_view_mocker(self, callback):
        view_mocker = self.object.get('view_mocker', lambda a: a)
        if isinstance(view_mocker, six.string_types):
            view_mocker = self._load_class(view_mocker, callback)
        return view_mocker

    def get_yaml_parameters(self, callback, docstring_param_name='parameters'):
        """
        Retrieves parameters from YAML object
        """
        params = []
        fields = self.object.get(docstring_param_name, [])
        for field in fields:
            param_type = field.get('in', None)
            if param_type not in self.PARAM_TYPES:
                param_type = 'formData'

            # Data Type & Format
            # See:
            # https://github.com/wordnik/swagger-core/wiki/1.2-transition#wiki-additions-2
            # https://github.com/wordnik/swagger-core/wiki/Parameters
            data_type = field.get('type', 'string')
            pytype = field.get('pytype', None)
            if pytype is not None:
                try:
                    serializer = self._load_class(pytype, callback)
                    data_type = get_serializer_name(
                        serializer)
                except (ImportError, ValueError):
                    pass

            # Data Format
            data_format = field.get('format', None)

            f = {
                'in': param_type,
                'name': field.get('name', None),
                'description': field.get('description', ''),
                'required': field.get('required', False),
            }

            normalize_data_format(data_type, data_format, f)

            if field.get('collectionFormat', None):
                f['collectionFormat'] = field.get('collectionFormat', False)

            if field.get('default', None) is not None:
                f['default'] = field.get('default', None)

            if f['type'] == 'array':
                items = field.get('items', {})
                elt_data_type = items.get('type', 'string')
                elt_data_format = items.get('type', 'format')
                f['items'] = {
                }
                normalize_data_format(elt_data_type, elt_data_format, f['items'])

                unique_items = field.get('uniqueItems', None)
                if unique_items is not None:
                    f['uniqueItems'] = unique_items

            # Min/Max are optional
            if 'minimum' in field and data_type == 'integer':
                f['minimum'] = str(field.get('minimum', 0))

            if 'maximum' in field and data_type == 'integer':
                f['maximum'] = str(field.get('maximum', 0))

            # enum options
            enum = field.get('enum', [])
            if enum:
                f['enum'] = enum

            # File support
            if f['type'] == 'file':
                f['in'] = 'body'

            params.append(f)

        return params

    def discover_parameters(self, inspector):
        """
        Applies parameters strategy for parameters discovered
        from method and docstring
        """
        parameters = []
        docstring_params = self.get_yaml_parameters(inspector.callback)
        method_params = inspector.get_parameters()

        # in may differ, overwrite first
        # so strategy can be applied
        for meth_param in method_params:
            for doc_param in docstring_params:
                if doc_param['name'] == meth_param['name']:
                    if 'in' in doc_param:
                        meth_param['in'] = doc_param['in']

        for param_type in self.PARAM_TYPES:
            if self.should_omit_parameters(param_type):
                continue
            parameters += self._apply_strategy(
                param_type, method_params, docstring_params
            )

        # PATCH requests expects all fields except path fields to be optional
        if inspector.get_http_method() == "PATCH":
            for param in parameters:
                if param['in'] != 'path':
                    param['required'] = False

        return parameters

    def discover_querystring_parameters(self, inspector):
        return self.get_yaml_parameters(inspector.callback, docstring_param_name='querystring_parameters')

    def should_omit_parameters(self, param_type):
        """
        Checks if particular parameter types should be omitted explicitly
        """
        return param_type in self.object.get('omit_parameters', [])

    def should_omit_serializer(self):
        """
        Checks if serializer should be intentionally omitted
        """
        return self.object.get('omit_serializer', False)

    def _apply_strategy(self, param_type, method_params, docstring_params):
        """
        Applies strategy for subset of parameters filtered by `in`
        """
        strategy = self.get_parameters_strategy(param_type=param_type)
        method_params = self._filter_params(
            params=method_params,
            key='in',
            val=param_type
        )
        docstring_params = self._filter_params(
            params=docstring_params,
            key='in',
            val=param_type
        )

        if strategy == 'replace':
            return docstring_params or method_params
        elif strategy == 'merge':
            return self._merge_params(
                method_params,
                docstring_params,
                key='name',
            )

        return []

    @staticmethod
    def _filter_params(params, key, val):
        """
        Returns filter function for parameters structure
        """
        def filter_by(o):
            return o.get(key, None) == val
        return filter(filter_by, params)

    @staticmethod
    def _merge_params(params1, params2, key):
        """
        Helper method.
        Merges parameters lists by key
        """
        import itertools
        merged = OrderedDict()
        for item in itertools.chain(params1, params2):
            merged[item[key]] = item

        return [val for (_, val) in merged.items()]

    def get_parameters_strategy(self, param_type=None):
        """
        Get behaviour strategy for parameter types.

        It can be either `merge` or `replace`:
            - `merge` overwrites duplicate parameters signatures
                discovered by inspector with the ones defined explicitly in
                docstring
            - `replace` strategy completely overwrites parameters discovered
                by inspector with the ones defined explicitly in docstring.

        Note: Strategy can be defined per `in` so `path` parameters can
        use `merge` strategy while `form` parameters will use `replace`
        strategy.

        Default strategy: `merge`
        """
        default = 'merge'
        strategy = self.object.get('parameters_strategy', default)
        if hasattr(strategy, 'get') and param_type is not None:
            strategy = strategy.get(param_type, default)

        if strategy not in ['merge', 'replace']:
            strategy = default

        return strategy

    def get_param(self, param_name, default):
        """
        :param param_name: lookup parameter
        :type param_name: string
        :param default: default value if parameter not found
        :return : a single parameter found in the docstring
        """
        return self.object.get(param_name, default)

    def force_pagination(self):
        return self.object.get('force_pagination', False)
