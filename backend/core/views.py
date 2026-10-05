from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft
from .serializers import ClothRollSerializer, DipRunSerializer, LoftSerializer


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs


def _fmt_pct(value):
    if value is None:
        return "0.00"
    return str(Decimal(value).quantize(Decimal("0.01")))


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError:
            # 两名浸胶工并发给同一布卷登记：唯一约束只放行一笔
            return Response(
                {"detail": "该布卷当日已登记浸渍，重复登记不入库"},
                status=status.HTTP_409_CONFLICT,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=False, methods=["get"], url_path="daily-total")
    def daily_total(self, request):
        """当日树脂加总：本间今天新登记浸渍的条数与树脂百分比合计（只读）。"""
        today = timezone.localdate()
        todays = DipRun.objects.filter(dip_date=today).select_related(
            "roll", "roll__loft"
        )
        by_loft = (
            todays.values("roll__loft_id", "roll__loft__name")
            .annotate(count=Count("id"), resin_sum=Sum("resin_pct"))
            .order_by("roll__loft_id")
        )
        lofts = [
            {
                "loftId": row["roll__loft_id"],
                "loftName": row["roll__loft__name"],
                "count": row["count"],
                "resinPctSum": _fmt_pct(row["resin_sum"]),
            }
            for row in by_loft
        ]
        total = todays.aggregate(count=Count("id"), resin_sum=Sum("resin_pct"))
        return Response(
            {
                "date": today.isoformat(),
                "totalCount": total["count"],
                "totalResinPct": _fmt_pct(total["resin_sum"]),
                "lofts": lofts,
                "entries": DipRunSerializer(todays, many=True).data,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
