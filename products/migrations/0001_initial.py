# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-04-12 15:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(verbose_name='Description')),
                ('price', models.FloatField(verbose_name='Price in EUR')),
                ('color', models.PositiveIntegerField(choices=[(1, b'red'), (2, b'blue'), (3, b'white')], verbose_name='Color')),
                ('created_date', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Creation Date')),
                ('in_stock', models.BooleanField(verbose_name='Is available in stock')),
            ],
        ),
    ]
