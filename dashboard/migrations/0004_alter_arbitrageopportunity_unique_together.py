# Generated by Django 5.1 on 2024-12-21 20:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_arbitrageopportunity_route'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='arbitrageopportunity',
            unique_together={('pair_1', 'pair_2', 'pair_3')},
        ),
    ]
