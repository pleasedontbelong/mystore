# -*- coding: utf-8 -*-
from django.conf import settings


class SwaggerConfig(object):
    DEFAULT_SWAGGER_SETTINGS = {
        'exclude_namespaces': [],
        'exclude_module_paths': [],
        'exclude_url_patterns': [],
        'exclude_url_patterns_names': [],
        'include_module_paths': [],
        'requires_authentication': False,
        'requires_superuser': False,
        'base_path': ''
    }

    def __init__(self):
        super(SwaggerConfig, self).__init__()
        self.global_settings = self.DEFAULT_SWAGGER_SETTINGS.copy()
        self.global_settings.update(settings.SWAGGER_GLOBAL_SETTINGS)

    def get_config(self, config_name=None):
        config_name = config_name or "default"
        if config_name not in settings.SWAGGER_LOCAL_SETTINGS:
            raise Exception("{} swagger settings not defined".format(config_name))
        current_config = self.global_settings.copy()
        current_config.update(settings.SWAGGER_LOCAL_SETTINGS[config_name])
        return current_config
