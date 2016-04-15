from django.core.exceptions import PermissionDenied
from .config import SwaggerConfig

from rest_framework.views import Response, APIView
from rest_framework.settings import api_settings
from rest_framework.permissions import AllowAny

from .urlparser import UrlParser
from .docgenerator import DocumentationGenerator

try:
    JSONRenderer = list(filter(
        lambda item: item.format == 'json',
        api_settings.DEFAULT_RENDERER_CLASSES,
    ))[0]
except IndexError:
    from rest_framework.renderers import JSONRenderer


class Swagger2JSONView(APIView):
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer, )

    def get(self, request, *args, **kwargs):
        swagger_config_name = kwargs.get('swagger_config_name')
        self.check_permission(request, swagger_config_name)
        paths = self.get_paths()
        generator = DocumentationGenerator(
            for_user=request.user,
            config=self.config,
            config_name=swagger_config_name,
            request=request
        )
        return Response(generator.get_root(paths))

    def get_paths(self):
        urlparser = UrlParser(self.config, self.request)
        return urlparser.get_apis()

    def check_permission(self, request, swagger_config_name):
        self.config = SwaggerConfig().get_config(swagger_config_name)
        if not self.has_permission(request):
            raise PermissionDenied()

    def has_permission(self, request):
        if self.config['requires_superuser'] and not request.user.is_superuser:
            return False
        if self.config['requires_authentication'] and not request.user.is_authenticated():
            return False
        return True
