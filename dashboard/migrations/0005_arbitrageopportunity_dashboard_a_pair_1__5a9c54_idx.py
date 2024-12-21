# Generated by Django 5.1 on 2024-12-21 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_alter_arbitrageopportunity_unique_together'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='arbitrageopportunity',
            index=models.Index(fields=['pair_1', 'pair_2', 'pair_3'], name='dashboard_a_pair_1__5a9c54_idx'),
        ),
    ]
