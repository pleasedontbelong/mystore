from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        swagger_name = "Product"
        _in = "body"
        model = Product
        fields = ('id', 'name', 'description', 'price', 'color', 'created_date', 'in_stock')
        read_only = ('id',)
