from importlib import import_module
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern
from django.contrib.admindocs.views import simplify_regex
from django.conf import settings

from rest_framework.views import APIView


class UrlParser(object):

    def __init__(self, config, request):
        self.urlconf = settings.ROOT_URLCONF
        self.exclude_namespaces = config.get('exclude_namespaces', [])
        self.exclude_module_paths = config.get('exclude_module_paths', [])
        self.include_module_paths = config.get('include_module_paths', [])
        self.exclude_url_patterns = config.get('exclude_url_patterns', [])
        self.exclude_url_patterns_names = config.get('exclude_url_patterns_names', [])

    def get_apis(self):
        """
        Returns all the DRF APIViews found in the project URLs
        """
        urls = import_module(self.urlconf)
        return self.__flatten_patterns_tree__(urls.urlpatterns)

    def __assemble_endpoint_data__(self, pattern, prefix=''):
        """
        Creates a dictionary for matched API urls

        pattern -- the pattern to parse
        prefix -- the API path prefix (used by recursion)
        """
        callback = self.__get_pattern_api_callback__(pattern)

        if callback is None or self.__exclude_router_api_root__(callback):
            return

        path = simplify_regex(prefix + pattern.regex.pattern)
        path = path.replace('<', '{').replace('>', '}')

        if self.__exclude_format_endpoints__(path):
            return

        return {
            'path': path,
            'pattern': pattern,
            'callback': callback,
        }

    def __flatten_patterns_tree__(self, patterns, prefix=''):
        """
        Uses recursion to flatten url tree.

        patterns -- urlpatterns list
        prefix -- (optional) Prefix for URL pattern
        """
        pattern_list = []

        for pattern in patterns:

            if isinstance(pattern, RegexURLPattern):
                endpoint_data = self.__assemble_endpoint_data__(pattern, prefix)

                if endpoint_data is None:
                    continue

                if any(excluded in endpoint_data['path'] for excluded in self.exclude_url_patterns):
                    continue

                if endpoint_data['pattern'].name in self.exclude_url_patterns_names:
                    continue

                pattern_list.append(endpoint_data)

            elif isinstance(pattern, RegexURLResolver):
                api_urls_module = pattern.urlconf_name.__name__ if hasattr(pattern.urlconf_name, '__name__') else ""
                # only modules included on the include_module_paths list
                if self.include_module_paths and api_urls_module not in self.include_module_paths:
                    continue

                # except modules included on the exclude_module_paths list
                if api_urls_module in self.exclude_module_paths:
                    continue

                if pattern.namespace is not None and pattern.namespace in self.exclude_namespaces:
                    continue

                pref = prefix + pattern.regex.pattern
                pattern_list.extend(self.__flatten_patterns_tree__(
                    pattern.url_patterns,
                    prefix=pref
                ))

        return pattern_list

    def __get_pattern_api_callback__(self, pattern):
        """
        Verifies that pattern callback is a subclass of APIView, and returns the class
        Handles older django & django rest 'cls_instance'
        """
        if not hasattr(pattern, 'callback'):
            return

        if (hasattr(pattern.callback, 'cls') and
                issubclass(pattern.callback.cls, APIView)):
            return pattern.callback.cls

        elif (hasattr(pattern.callback, 'cls_instance') and
                isinstance(pattern.callback.cls_instance, APIView)):
            return pattern.callback.cls_instance

    def __exclude_router_api_root__(self, callback):
        """
        Returns True if the URL's callback is rest_framework.routers.APIRoot
        """
        return callback.__module__ == 'rest_framework.routers'

    def __exclude_format_endpoints__(self, path):
        """
        Excludes URL patterns that contain .{format}
        """
        return '.{format}' in path
