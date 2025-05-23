# Generated by Django 5.2 on 2025-04-20 20:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_wallet'),
    ]

    operations = [
        migrations.CreateModel(
            name='SimulatedTrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20)),
                ('side', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')], max_length=4)),
                ('qty', models.DecimalField(decimal_places=8, max_digits=20)),
                ('price', models.DecimalField(decimal_places=8, max_digits=20)),
                ('total', models.DecimalField(decimal_places=8, max_digits=20)),
                ('ts', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
