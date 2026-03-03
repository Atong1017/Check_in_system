from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Company, Shop

User = get_user_model()

class Command(BaseCommand):
    help = "Generate mock data including superuser and demo roles"

    def handle(self, *args, **options):
        # 1. 建立公司與分店
        company, _ = Company.objects.get_or_create(name="示範總公司")
        shop, _ = Shop.objects.get_or_create(company=company, name="敦南旗艦店", defaults={'is_24h': True})

        # 2. 建立超級管理員 (Django Admin)
        if not User.objects.filter(username="superuser").exists():
            User.objects.create_superuser("superuser", "admin@example.com", "admin1234")
            self.stdout.write(self.style.SUCCESS("  [OK] 建立超級管理員: superuser / admin1234"))

        # 3. 建立 BOSS (總公司負責人)
        if not User.objects.filter(username="boss").exists():
            User.objects.create_user(
                username="boss", 
                password="password123", 
                role=User.Role.ADMIN, 
                company=company,
                is_staff=True,
                first_name="老闆"
            )
            self.stdout.write(self.style.SUCCESS("  [OK] 建立總公司負責人: boss / password123"))

        # 4. 建立 Mami (店長)
        if not User.objects.filter(username="mami").exists():
            User.objects.create_user(
                username="mami", 
                password="password123", 
                role=User.Role.MAMI, 
                shop=shop,
                employee_code="M001",
                first_name="店長媽咪"
            )
            self.stdout.write(self.style.SUCCESS("  [OK] 建立店長: mami / password123"))

        # 5. 建立 Agent (經紀人)
        if not User.objects.filter(username="agent").exists():
            User.objects.create_user(
                username="agent", 
                password="password123", 
                role=User.Role.AGENT, 
                shop=shop,
                employee_code="A001",
                first_name="經紀人阿傑"
            )
            self.stdout.write(self.style.SUCCESS("  [OK] 建立經紀人: agent / password123"))

        # 6. 建立 Staff (員工)
        if not User.objects.filter(username="staff").exists():
            User.objects.create_user(
                username="staff", 
                password="password123", 
                role=User.Role.STAFF, 
                shop=shop,
                employee_code="S001",
                first_name="員工小美"
            )
            self.stdout.write(self.style.SUCCESS("  [OK] 建立員工: staff / password123"))

        self.stdout.write(self.style.SUCCESS("\n🎉 模擬資料建立完成！你現在可以用以上帳號登入了。"))
