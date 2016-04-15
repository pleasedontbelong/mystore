from django.conf.urls import patterns
from django.conf.urls import url
from .views import Swagger2JSONView

urlpatterns = patterns(
    '',
    url(
        r'^(?P<swagger_config_name>[\w]+)/swagger\.json$',
        Swagger2JSONView.as_view(),
        name='django.swagger.2.0.json.view'
    ),
    url(
        r'^swagger\.json$',
        Swagger2JSONView.as_view(),
        name='django.swagger.2.0.json.view'
    )
)
