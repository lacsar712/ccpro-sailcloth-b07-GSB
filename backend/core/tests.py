from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ClothRoll, DipRun, Loft

User = get_user_model()
SH = ZoneInfo("Asia/Shanghai")


class DipRunDedupTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="worker1", password="x")
        self.client.force_authenticate(self.user)
        self.loft = Loft.objects.create(name="北岸帆布间")
        self.roll = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-01", status=ClothRoll.STATUS_DIPPING
        )
        self.roll_b = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-02", status=ClothRoll.STATUS_DIPPING
        )

    def test_db_blocks_second_dip_same_roll_same_local_day(self):
        DipRun.objects.create(
            roll=self.roll,
            started_at=datetime(2026, 10, 4, 10, 0, tzinfo=SH),
            resin_pct=Decimal("28.50"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DipRun.objects.create(
                    roll=self.roll,
                    started_at=datetime(2026, 10, 4, 12, 0, tzinfo=SH),
                    resin_pct=Decimal("30.00"),
                )
        self.assertEqual(DipRun.objects.filter(roll=self.roll).count(), 1)

    def test_local_day_boundary_uses_shanghai_midnight(self):
        # 23:50 与次日 00:10（本地）属不同自然日，可各登一笔。
        DipRun.objects.create(
            roll=self.roll,
            started_at=datetime(2026, 10, 4, 23, 50, tzinfo=SH),
            resin_pct=Decimal("28.00"),
        )
        DipRun.objects.create(
            roll=self.roll,
            started_at=datetime(2026, 10, 5, 0, 10, tzinfo=SH),
            resin_pct=Decimal("29.00"),
        )
        self.assertEqual(DipRun.objects.filter(roll=self.roll).count(), 2)

    def test_two_workers_same_roll_only_one_row_via_api(self):
        url = reverse("dip-list")
        payload = {
            "rollId": self.roll.id,
            "startedAt": datetime(2026, 10, 4, 9, 0, tzinfo=SH).isoformat(),
            "resinPct": "28.00",
        }
        r1 = self.client.post(url, payload, format="json")
        # 第二名浸胶工交叉给同一原布再点一笔（树脂值还填得不一样）。
        payload2 = {**payload, "resinPct": "31.50"}
        r2 = self.client.post(url, payload2, format="json")

        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertTrue(r2.data.get("deduplicated"))
        # 幂等返回的是先入库那笔，树脂没有被第二笔改掉。
        self.assertEqual(str(r2.data["resinPct"]), "28.00")
        self.assertEqual(r2.data["id"], r1.data["id"])
        # 关键验收：只许一笔入库，条数必须是 1。
        self.assertEqual(DipRun.objects.filter(roll=self.roll).count(), 1)
        self.assertEqual(DipRun.objects.count(), 1)

    def test_different_rolls_same_day_both_persist(self):
        url = reverse("dip-list")
        now = timezone.now().isoformat()
        a = self.client.post(
            url, {"rollId": self.roll.id, "startedAt": now, "resinPct": "28.00"},
            format="json",
        )
        b = self.client.post(
            url, {"rollId": self.roll_b.id, "startedAt": now, "resinPct": "26.00"},
            format="json",
        )
        self.assertEqual(a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(b.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DipRun.objects.count(), 2)

    def test_dips_endpoint_rejects_mutation(self):
        dip = DipRun.objects.create(
            roll=self.roll, started_at=timezone.now(), resin_pct=Decimal("28.00")
        )
        url = reverse("dip-detail", args=[dip.id])
        self.assertEqual(
            self.client.patch(url, {"resinPct": "99.00"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.put(
                url,
                {
                    "rollId": self.roll.id,
                    "startedAt": timezone.now().isoformat(),
                    "resinPct": "99.00",
                },
                format="json",
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        dip.refresh_from_db()
        self.assertEqual(dip.resin_pct, Decimal("28.00"))


class ResinTotalTodayTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="worker2", password="x")
        self.client.force_authenticate(self.user)
        self.loft = Loft.objects.create(name="北岸帆布间")
        self.r1 = ClothRoll.objects.create(loft=self.loft, roll_code="R-01")
        self.r2 = ClothRoll.objects.create(loft=self.loft, roll_code="R-02")

    def test_total_tracks_new_registrations_and_matches_records(self):
        url = reverse("resin-total-today")

        def fetch():
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            return resp.data

        data = fetch()
        self.assertEqual(data["count"], 0)
        self.assertEqual(Decimal(data["resinPctTotal"]), Decimal("0"))
        self.assertEqual(data["items"], [])

        now = timezone.now()
        # 在面板新登一笔，再打开加总台：条数与合计必须跟上。
        DipRun.objects.create(
            roll=self.r1, started_at=now, resin_pct=Decimal("28.50")
        )
        data = fetch()
        self.assertEqual(data["count"], 1)
        self.assertEqual(Decimal(data["resinPctTotal"]), Decimal("28.50"))

        DipRun.objects.create(
            roll=self.r2, started_at=now - timedelta(minutes=3),
            resin_pct=Decimal("26.00"),
        )
        data = fetch()
        # 合计必须跟流水里今天的记录逐条加得上。
        expected = sum(
            (Decimal(row["resinPct"]) for row in data["items"]), Decimal("0")
        )
        self.assertEqual(data["count"], 2)
        self.assertEqual(Decimal(data["resinPctTotal"]), Decimal("54.50"))
        self.assertEqual(Decimal(data["resinPctTotal"]), expected)
        self.assertEqual(len(data["items"]), data["count"])

    def test_yesterday_excluded(self):
        DipRun.objects.create(
            roll=self.r1,
            started_at=timezone.now() - timedelta(days=1, hours=2),
            resin_pct=Decimal("40.00"),
        )
        resp = self.client.get(reverse("resin-total-today"))
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(Decimal(resp.data["resinPctTotal"]), Decimal("0"))

    def test_total_endpoint_is_read_only(self):
        url = reverse("resin-total-today")
        self.assertEqual(
            self.client.post(url, {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.patch(url, {"resinPct": "99"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        resp = self.client.get(reverse("resin-total-today"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
