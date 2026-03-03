from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from core.models import Company, Shop, User, Table, WorkMode


class Command(BaseCommand):
    help = "建立示範資料：公司、分店、各角色使用者（冪等，重複執行不會重複建立）"

    # 預設密碼，可透過 --password 覆寫
    DEFAULT_PASSWORD = "demo1234"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=self.DEFAULT_PASSWORD,
            help=f"設定所有示範帳號的密碼（預設：{self.DEFAULT_PASSWORD}）",
        )

    def handle(self, *args, **options):
        password = options["password"]

        # ── 1. 建立公司 ──
        company, _ = Company.objects.get_or_create(
            name="Demo 總公司",
            defaults={"is_active": True},
        )
        self.stdout.write(f"  [OK] 總公司: {company.name}")

        # ── 2. 建立分店 ──
        shop_a, _ = Shop.objects.get_or_create(
            company=company, name="Demo 一店",
        )
        shop_b, _ = Shop.objects.get_or_create(
            company=company, name="Demo 二店",
        )
        self.stdout.write(f"  [OK] 分店: {shop_a.name}, {shop_b.name}")

        # ── 3. 建立桌次 ──
        for shop in [shop_a, shop_b]:
            for i in range(1, 4):
                Table.objects.get_or_create(
                    shop=shop, name=f"桌{i}",
                    defaults={"is_active": True},
                )
        self.stdout.write("  [OK] 桌次已建立（每店 3 桌）")

        # ── 4. 建立上班模式 ──
        wm, _ = WorkMode.objects.get_or_create(
            shop=shop_a, name="月制 160H",
            defaults={"period_type": "monthly", "total_hours": 160},
        )
        self.stdout.write(f"  [OK] 上班模式: {wm.name}")

        # ── 5. 建立各角色使用者 ──
        demo_users = [
            # (username, role, first_name, company, shop, employee_code, is_superuser)
            ("admin",    "admin", "管理員",   company, None,   "",       True),
            ("mami01",   "mami",  "媽咪A",   None,    shop_a, "MAMI01", False),
            ("mami02",   "mami",  "媽咪B",   None,    shop_b, "MAMI02", False),
            ("agent01",  "agent", "經紀人A",  None,    shop_a, "AGT01",  False),
            ("staff01",  "staff", "員工A",    None,    shop_a, "STF01",  False),
            ("staff02",  "staff", "員工B",    None,    shop_a, "STF02",  False),
            ("staff03",  "staff", "員工C",    None,    shop_b, "STF03",  False),
        ]

        for username, role, first_name, comp, shop, emp_code, is_su in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "first_name": first_name,
                    "company": comp,
                    "shop": shop,
                    "employee_code": emp_code,
                    "is_staff": is_su,
                    "is_superuser": is_su,
                },
            )
            if created:
                user.set_password(password)
                user.save()

            # 加入對應 Group
            group_name = role.capitalize()  # admin→Admin, mami→Mami ...
            group = Group.objects.filter(name=group_name).first()
            if group and not user.groups.filter(pk=group.pk).exists():
                user.groups.add(group)

            tag = "NEW" if created else "EXISTS"
            self.stdout.write(f"  [{tag}] {role:6s} | {username:10s} | {first_name}")

        # 把 staff01, staff02 加到上班模式
        for uname in ["staff01", "staff02"]:
            u = User.objects.filter(username=uname).first()
            if u and not wm.users.filter(pk=u.pk).exists():
                wm.users.add(u)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== 示範資料建立完成 ==="))
        self.stdout.write(f"  所有帳號密碼: {password}")
        self.stdout.write("")
        self.stdout.write("  帳號列表:")
        self.stdout.write("  ─────────────────────────────────────")
        self.stdout.write("  admin    (超級管理員) — 總公司層級")
        self.stdout.write("  mami01   (媽咪/店長)  — Demo 一店")
        self.stdout.write("  mami02   (媽咪/店長)  — Demo 二店")
        self.stdout.write("  agent01  (經紀人)     — Demo 一店")
        self.stdout.write("  staff01  (員工)       — Demo 一店")
        self.stdout.write("  staff02  (員工)       — Demo 一店")
        self.stdout.write("  staff03  (員工)       — Demo 二店")
        self.stdout.write("  ─────────────────────────────────────")
