# dashboard/api.py
from rest_framework import serializers, viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import TradingSignal


class TradingSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingSignal
        fields = ["id", "symbol", "signal_type", "price", "timestamp", "meta"]


class TradingSignalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/trading-signals/?symbol=BTCUSDT&signal_type=BUY
    /api/trading-signals/?timestamp__gte=2025-04-19T00:00
    """
    queryset = TradingSignal.objects.all().order_by("-timestamp")
    serializer_class = TradingSignalSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        "symbol": ["exact"],
        "signal_type": ["exact"],
        "timestamp": ["gte", "lte"],
    }
    ordering_fields = ["timestamp", "price"]
