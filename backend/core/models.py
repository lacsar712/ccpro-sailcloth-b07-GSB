from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.db.models.functions import TruncDate


class LocalDipDate(TruncDate):
    """按配置时区（Asia/Shanghai）截取浸渍开始时间的本地自然日。

    构造时固定注入 settings.TIME_ZONE，使 UniqueConstraint 的「同一本地
    自然日」不依赖运行时当前时区。
    """

    def __init__(self, expression, output_field=None, **extra):
        super().__init__(
            expression,
            tzinfo=ZoneInfo(settings.TIME_ZONE),
            output_field=output_field,
            **extra,
        )

    def deconstruct(self):
        # tzinfo（ZoneInfo）无法序列化进迁移，只写表达式；
        # __init__ 会自行补回时区。
        path = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return (path, self.source_expressions, {})


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            # 同一原布同一本地自然日只许入库一笔浸渍：
            # 两名浸胶工交叉连点各登一笔时，数据库层挡下第二笔。
            models.UniqueConstraint(
                LocalDipDate("started_at"),
                "roll",
                name="uniq_one_dip_per_roll_per_day",
            ),
        ]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"
