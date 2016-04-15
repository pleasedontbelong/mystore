from django.conf.urls import url
from products import views

urlpatterns = [
    url(
        r'^products$',
        views.ProductListCreateView.as_view(),
        name='product-list-create'
    ),
    url(
        r'^products/(?P<product_id>[0-9]+)$',
        views.ProductRetrieveUpdateDestroyView.as_view(),
        name='product-detail'
    ),
]
