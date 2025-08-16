from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'デモ用の管理者ユーザーを作成します'

    def handle(self, *args, **options):
        username = 'admin'
        email = 'admin@bookiniad.com'
        password = 'admin123'

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'ユーザー "{username}" は既に存在します')
            )
        else:
            User.objects.create_superuser(username, email, password)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ 管理者ユーザーを作成しました\n'
                    f'   ユーザー名: {username}\n'
                    f'   パスワード: {password}\n'
                    f'   メール: {email}'
                )
            )
