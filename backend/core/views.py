from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft
from .serializers import ClothRollSerializer, DipRunSerializer, LoftSerializer


def local_day_bounds(moment=None):
    """返回配置时区（Asia/Shanghai）下某时刻所属自然日的 [起, 止) UTC 边界。"""
    tz = ZoneInfo(settings.TIME_ZONE)
    if moment is None:
        moment = timezone.now()
    local_day = moment.astimezone(tz).date()
    start = datetime.combine(local_day, time.min, tzinfo=tz)
    return local_day, start, start + timedelta(days=1)


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


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    # 浸渍记录只增不改：不开放 put/patch/delete，杜绝事后改树脂、改时长。
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
                serializer.save()
        except IntegrityError:
            # 同一原布同一本地日唯一约束：两名浸胶工交叉连点各登一笔时，
            # 第二笔被数据库挡下，幂等返回当日已入库的那笔，绝不写第二条。
            roll = serializer.validated_data["roll"]
            started_at = serializer.validated_data["started_at"]
            _, day_start, day_end = local_day_bounds(started_at)
            existing = (
                DipRun.objects.select_related("roll", "roll__loft")
                .filter(
                    roll=roll,
                    started_at__gte=day_start,
                    started_at__lt=day_end,
                )
                .order_by("id")
                .first()
            )
            if existing is None:
                raise
            data = self.get_serializer(existing).data
            data["deduplicated"] = True
            return Response(data, status=200)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resin_total_today(request):
    """当日树脂加总：条数与树脂百分比合计均实时聚合，不允许任何写入。"""
    local_day, day_start, day_end = local_day_bounds()
    today_qs = DipRun.objects.select_related("roll", "roll__loft").filter(
        started_at__gte=day_start,
        started_at__lt=day_end,
    )
    agg = today_qs.aggregate(
        count=Count("id"),
        resin_total=Sum("resin_pct"),
    )
    items = DipRunSerializer(today_qs.order_by("-started_at", "-id"), many=True).data
    return Response(
        {
            "date": local_day.isoformat(),
            "timezone": settings.TIME_ZONE,
            "count": agg["count"] or 0,
            "resinPctTotal": str(agg["resin_total"] or Decimal("0")),
            "items": items,
        }
    )
