from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _
from .constants import PRODUCT_COLORS


class Product(models.Model):

    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"))
    price = models.FloatField(_("Price in EUR"))
    color = models.PositiveIntegerField(_("Color"), choices=PRODUCT_COLORS)
    created_date = models.DateTimeField(_("Creation Date"), blank=True, null=True, auto_now=True)
    in_stock = models.BooleanField(_("Is available in stock"))

    def __unicode__(self):
        return self.name
