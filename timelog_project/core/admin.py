from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Company, User, Shop, Attendance, SalaryDamage, Table, TableSession, WorkMode


# ─────────────────────────────────────────────
# Inline: Shop 顯示在 Company 內
# ─────────────────────────────────────────────
class ShopInline(admin.TabularInline):
    model = Shop
    extra = 0
    fields = ("name", "is_24h")
    show_change_link = True


# ─────────────────────────────────────────────
# Inline: TableSession 顯示在 Attendance 內
# ─────────────────────────────────────────────
class TableSessionInline(admin.TabularInline):
    model = TableSession
    extra = 0
    fields = ("table", "start_time", "end_time")
    show_change_link = True


# ─────────────────────────────────────────────
# Company Admin
# ─────────────────────────────────────────────
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "shop_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [ShopInline]

    @admin.display(description="分店數")
    def shop_count(self, obj):
        return obj.shops.count()


# ─────────────────────────────────────────────
# Shop Admin
# ─────────────────────────────────────────────
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "is_24h")
    list_filter = ("company", "is_24h")
    search_fields = ("name", "company__name")


# ─────────────────────────────────────────────
# User Admin
# ─────────────────────────────────────────────
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "role", "employee_code", "company", "shop", "is_active")
    list_filter = ("role", "company", "shop", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "employee_code")
    ordering = ("company", "shop", "role", "username")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("公司、分店與角色", {
            "fields": ("role", "company", "shop", "employee_code"),
            "description": "BOSS 填 company 即可；Mami/Agent/Staff 填 shop（company 可留空，系統自動從分店推算）",
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("公司、分店與角色", {
            "fields": ("role", "company", "shop", "employee_code"),
        }),
    )


# ─────────────────────────────────────────────
# Attendance Admin
# ─────────────────────────────────────────────
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user", "clock_in", "clock_out", "work_segment",
        "status", "duration_hours_display",
    )
    list_filter = ("status", "work_segment", "user__shop", "user__shop__company")
    search_fields = ("user__username", "user__first_name", "note")
    date_hierarchy = "clock_in"
    ordering = ("-clock_in",)
    readonly_fields = ("duration_hours_display",)
    inlines = [TableSessionInline]

    fieldsets = (
        ("出勤資訊", {
            "fields": ("user", "clock_in", "clock_out", "work_segment"),
        }),
        ("補簽申請", {
            "fields": ("status", "note", "proof"),
            "classes": ("collapse",),
        }),
        ("計算資訊", {
            "fields": ("duration_hours_display",),
        }),
    )

    @admin.display(description="工時 (小時)")
    def duration_hours_display(self, obj):
        hours = obj.duration_hours
        return f"{hours} hrs" if hours is not None else "尚未打下班"


# ─────────────────────────────────────────────
# SalaryDamage Admin
# ─────────────────────────────────────────────
@admin.register(SalaryDamage)
class SalaryDamageAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "amount", "date", "description")
    list_filter = ("type", "user__shop__company", "user__shop", "date")
    search_fields = ("user__username", "description")
    date_hierarchy = "date"
    ordering = ("-date",)


# ─────────────────────────────────────────────
# Table Admin
# ─────────────────────────────────────────────
@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "get_company", "is_active")
    list_filter = ("shop__company", "shop", "is_active")
    search_fields = ("name", "shop__name", "shop__company__name")

    @admin.display(description="總公司", ordering="shop__company__name")
    def get_company(self, obj):
        return obj.shop.company.name


# ─────────────────────────────────────────────
# TableSession Admin
# ─────────────────────────────────────────────
@admin.register(TableSession)
class TableSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "table", "attendance", "start_time", "end_time")
    list_filter = ("table__shop__company", "table__shop")
    search_fields = ("user__username", "table__name")
    ordering = ("-start_time",)


# ─────────────────────────────────────────────
# WorkMode Admin
# ─────────────────────────────────────────────
@admin.register(WorkMode)
class WorkModeAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "get_company", "period_type", "total_hours")
    list_filter = ("shop__company", "shop", "period_type")
    search_fields = ("name", "shop__name")
    filter_horizontal = ("users",)

    @admin.display(description="總公司", ordering="shop__company__name")
    def get_company(self, obj):
        return obj.shop.company.name
