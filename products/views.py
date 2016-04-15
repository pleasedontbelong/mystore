from rest_framework import generics
from .models import Product
from .serializers import ProductSerializer


class ProductListCreateView(generics.ListCreateAPIView):

    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def list(self, *args, **kwargs):
        """
        Lists the products
        ---
            tags:
                - Product
            operationId: listProducts
        """
        return super(ProductListCreateView, self).list(*args, **kwargs)

    def create(self, *args, **kwargs):
        """
        Creates a single product
        ---
            tags:
                - Product
            operationId: createProducts
        """
        return super(ProductListCreateView, self).create(*args, **kwargs)


class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):

    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def retrieve(self, *args, **kwargs):
        """
        Retrieves a single Product by ID
        ---
            tags:
                - Product
            operationId: retrieveProduct
        """
        return super(ProductRetrieveUpdateDestroyView, self).retrieve(*args, **kwargs)

    def update(self, *args, **kwargs):
        """
        Updates a product
        ---
            tags:
                - Product
            operationId: updateProduct
        """
        return super(ProductRetrieveUpdateDestroyView, self).update(*args, **kwargs)

    def destroy(self, *args, **kwargs):
        """
        Destroys a product
        ---
            tags:
                - Product
            operationId: destroyProduct
        """
        return super(ProductRetrieveUpdateDestroyView, self).destroy(*args, **kwargs)
