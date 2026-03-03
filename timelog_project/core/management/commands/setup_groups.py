from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


def get_perm(codename):
    try:
        return Permission.objects.get(codename=codename)
    except Permission.DoesNotExist:
        return None


class Command(BaseCommand):
    help = "Create default permission Groups for each role (idempotent)"

    def handle(self, *args, **options):
        self._setup_admin_group()
        self._setup_mami_group()
        self._setup_agent_group()
        self._setup_staff_group()
        self.stdout.write(self.style.SUCCESS("Permission groups created/updated successfully."))

    def _setup_admin_group(self):
        group, _ = Group.objects.get_or_create(name="Admin")
        group.permissions.set(Permission.objects.all())
        self.stdout.write("  [OK] Admin group")

    def _setup_mami_group(self):
        group, _ = Group.objects.get_or_create(name="Mami")
        codenames = [
            # Company — 只能查看自己的
            "view_company",
            # Shop — 管理旗下分店
            "manage_shop",
            "view_shop", "change_shop",
            # Users
            "manage_shop_users",
            "view_user", "add_user", "change_user",
            # Tables
            "manage_tables",
            "view_table", "add_table", "change_table",
            # TableSessions
            "assign_table",
            "view_tablesession", "add_tablesession", "change_tablesession",
            # Attendance
            "view_all_attendance",
            "approve_attendance_correction",
            "view_attendance", "change_attendance",
            # SalaryDamage
            "manage_salary_damage",
            "view_salarydamage", "add_salarydamage", "change_salarydamage",
            # WorkMode
            "manage_work_modes",
            "view_workmode", "add_workmode", "change_workmode",
        ]
        self._apply_perms(group, codenames)
        self.stdout.write("  [OK] Mami group")

    def _setup_agent_group(self):
        group, _ = Group.objects.get_or_create(name="Agent")
        codenames = [
            # Users — 管理旗下員工
            "manage_agent_employees",
            "view_user",
            # Attendance
            "view_attendance", "add_attendance", "change_attendance",
            "approve_attendance_correction",
            # Tables
            "assign_table",
            "view_tablesession", "add_tablesession", "change_tablesession",
            "view_table",
            # SalaryDamage — 查看
            "view_salarydamage",
        ]
        self._apply_perms(group, codenames)
        self.stdout.write("  [OK] Agent group")

    def _setup_staff_group(self):
        group, _ = Group.objects.get_or_create(name="Staff")
        codenames = [
            "view_attendance", "add_attendance",
            "view_tablesession",
            "view_salarydamage",
        ]
        self._apply_perms(group, codenames)
        self.stdout.write("  [OK] Staff group")

    def _apply_perms(self, group, codenames):
        perms = []
        for codename in codenames:
            perm = get_perm(codename)
            if perm:
                perms.append(perm)
            else:
                self.stdout.write(
                    self.style.WARNING(f"    WARNING: Permission '{codename}' not found, skipping.")
                )
        group.permissions.set(perms)
