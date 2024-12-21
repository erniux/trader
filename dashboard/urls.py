from django.urls import path
from . import views

urlpatterns = [
    path('arbitrage-opportunities/', views.arbitrage_opportunities_list, name='arbitrage_opportunities_list'),
    # Otras rutas...
]
