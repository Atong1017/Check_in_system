from django.contrib.auth.models import AbstractUser
from django.db import models


# ─────────────────────────────────────────────
# Company (總公司) — 最上層，每個客戶一筆
# ─────────────────────────────────────────────
class Company(models.Model):
    name = models.CharField(max_length=100, verbose_name="公司名稱")
    is_active = models.BooleanField(default=True, verbose_name="啟用中")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        verbose_name = "總公司"
        verbose_name_plural = "總公司列表"
        permissions = [
            ("manage_company", "Can manage company settings"),
            ("view_all_companies", "Can view all companies (platform admin)"),
        ]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# Shop (分店) — 屬於總公司
# ─────────────────────────────────────────────
class Shop(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="shops",
        verbose_name="所屬總公司",
    )
    name = models.CharField(max_length=100, verbose_name="店名")
    is_24h = models.BooleanField(default=False, verbose_name="24小時營業")

    class Meta:
        verbose_name = "分店"
        verbose_name_plural = "分店列表"
        unique_together = [("company", "name")]
        permissions = [
            ("manage_shop", "Can manage shop settings"),
        ]

    def __str__(self):
        return f"{self.company.name} — {self.name}"


# ─────────────────────────────────────────────
# User (繼承 AbstractUser)
# ─────────────────────────────────────────────
class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = "admin", "Boss/Admin (總管理)"
        MAMI = "mami", "Mami (店長)"
        AGENT = "agent", "Agent (經紀人)"
        STAFF = "staff", "Staff (員工)"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name="角色",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="所屬總公司",
        help_text="BOSS 層級直接綁定總公司；其他角色透過分店間接屬於總公司",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="所屬分店",
        help_text="Mami / Agent / Staff 必填；BOSS 可為空",
    )
    employee_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="員工編號",
        help_text="每店唯一，例如 YIBA",
    )

    class Meta:
        verbose_name = "用戶"
        verbose_name_plural = "用戶列表"
        constraints = [
            models.UniqueConstraint(
                fields=["shop", "employee_code"],
                condition=models.Q(employee_code__gt=""),
                name="unique_employee_code_per_shop",
            )
        ]
        permissions = [
            ("view_all_users", "Can view all users across shops"),
            ("manage_shop_users", "Can manage users within own shop"),
            ("manage_agent_employees", "Can manage own agent employees"),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def effective_company(self):
        """回傳使用者實際所屬的總公司（BOSS 直接綁定；其他透過分店取得）"""
        if self.company:
            return self.company
        if self.shop:
            return self.shop.company
        return None


# ─────────────────────────────────────────────
# Attendance (出勤記錄)
# ─────────────────────────────────────────────
class Attendance(models.Model):

    class Status(models.TextChoices):
        NORMAL = "normal", "正常"
        PENDING_CORRECTION = "pending_correction", "待審核補簽"
        APPROVED = "approved", "已核准"
        REJECTED = "rejected", "已拒絕"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name="員工",
    )
    clock_in = models.DateTimeField(verbose_name="上班時間")
    clock_out = models.DateTimeField(null=True, blank=True, verbose_name="下班時間")
    work_segment = models.IntegerField(
        choices=[(1, "第一班"), (2, "第二班")],
        default=1,
        verbose_name="班次",
    )
    note = models.TextField(blank=True, verbose_name="補簽說明")
    proof = models.ImageField(
        upload_to="attendance_proofs/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="補簽憑證",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NORMAL,
        verbose_name="狀態",
    )

    class Meta:
        verbose_name = "出勤記錄"
        verbose_name_plural = "出勤記錄列表"
        ordering = ["-clock_in"]
        permissions = [
            ("approve_attendance_correction", "Can approve attendance correction"),
            ("view_all_attendance", "Can view attendance for all employees"),
        ]

    def __str__(self):
        return f"{self.user} - {self.clock_in.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_hours(self):
        if self.clock_out and self.clock_in:
            delta = self.clock_out - self.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return None


# ─────────────────────────────────────────────
# SalaryDamage (薪資調整 / 損壞賠償)
# ─────────────────────────────────────────────
class SalaryDamage(models.Model):

    class EntryType(models.TextChoices):
        SALARY_ADD = "salary_add", "薪資加項"
        SALARY_DEDUCT = "salary_deduct", "薪資扣項"
        DAMAGE = "damage", "損壞賠償"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="salary_damages",
        verbose_name="員工",
    )
    type = models.CharField(
        max_length=20,
        choices=EntryType.choices,
        verbose_name="類型",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="金額 (TWD)",
    )
    description = models.TextField(verbose_name="說明")
    date = models.DateField(verbose_name="日期")

    class Meta:
        verbose_name = "薪資調整/損壞記錄"
        verbose_name_plural = "薪資調整/損壞記錄列表"
        ordering = ["-date"]
        permissions = [
            ("manage_salary_damage", "Can add/edit salary damage records"),
        ]

    def __str__(self):
        return f"{self.user} | {self.get_type_display()} | {self.amount} | {self.date}"


# ─────────────────────────────────────────────
# Table (桌次) — 屬於分店
# ─────────────────────────────────────────────
class Table(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="tables",
        verbose_name="所屬分店",
    )
    name = models.CharField(max_length=50, verbose_name="桌號/名稱")
    is_active = models.BooleanField(default=True, verbose_name="啟用中")

    class Meta:
        verbose_name = "桌次"
        verbose_name_plural = "桌次列表"
        unique_together = [("shop", "name")]
        permissions = [
            ("manage_tables", "Can manage tables within shop"),
        ]

    def __str__(self):
        return f"{self.shop} - {self.name}"


# ─────────────────────────────────────────────
# TableSession (員工桌次服務記錄)
# ─────────────────────────────────────────────
class TableSession(models.Model):
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="桌次",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="table_sessions",
        verbose_name="員工",
    )
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.CASCADE,
        related_name="table_sessions",
        verbose_name="出勤記錄",
    )
    start_time = models.DateTimeField(verbose_name="開始時間")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="結束時間")

    class Meta:
        verbose_name = "桌次服務記錄"
        verbose_name_plural = "桌次服務記錄列表"
        ordering = ["-start_time"]
        permissions = [
            ("assign_table", "Can assign employees to tables"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.table} ({self.start_time.strftime('%H:%M')})"


# ─────────────────────────────────────────────
# WorkMode (上班模式) — 屬於分店
# ─────────────────────────────────────────────
class WorkMode(models.Model):

    class PeriodType(models.TextChoices):
        WEEKLY = "weekly", "週期"
        MONTHLY = "monthly", "月期"

    name = models.CharField(max_length=100, verbose_name="模式名稱")
    period_type = models.CharField(
        max_length=10,
        choices=PeriodType.choices,
        default=PeriodType.MONTHLY,
        verbose_name="週期類型",
    )
    total_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="總時數",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="work_modes",
        verbose_name="所屬分店",
    )
    users = models.ManyToManyField(
        User,
        blank=True,
        related_name="work_modes",
        verbose_name="適用員工",
    )

    class Meta:
        verbose_name = "上班模式"
        verbose_name_plural = "上班模式列表"
        permissions = [
            ("manage_work_modes", "Can manage work modes"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_period_type_display()}, {self.total_hours}h)"
