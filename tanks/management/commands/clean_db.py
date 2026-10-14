from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection

from tanks.models import Nation, Level, Crewman, Tank, BattleRecord


class Command(BaseCommand):
    help = ('Удаляет бои, танки, обычных игроков, уровни и нации. '
            'Сотрудники и суперпользователи сохраняются, если не указан --delete-superusers.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-levels',
            action='store_true',
            help='Keep levels data (do not delete)',
        )
        parser.add_argument(
            '--keep-nations',
            action='store_true',
            help='Keep nations data (do not delete)',
        )
        parser.add_argument(
            '--delete-superusers',
            action='store_true',
            help='Also delete staff and superuser accounts (default: keep them)',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Do not ask for confirmation',
        )

    def handle(self, *args, **options):
        if not options['noinput']:
            answer = input('Это удалит данные из базы. Продолжить? [y/N] ')
            if answer.strip().lower() != 'y':
                self.stdout.write('Отменено')
                return

        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('STARTING DATABASE CLEANUP'))
        self.stdout.write(self.style.WARNING('='*50))
        
        battles_count = BattleRecord.objects.count()
        BattleRecord.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {battles_count} battle records'))
        
        tanks_count = Tank.objects.count()
        Tank.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {tanks_count} tanks'))
        
        if not options['delete_superusers']:
            # профили игроков (Crewman) удаляются каскадно вместе с пользователями
            users_to_delete = User.objects.filter(is_superuser=False, is_staff=False)
            users_count = users_to_delete.count()
            users_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {users_count} regular users'))
        else:
            users_count = User.objects.count()
            User.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {users_count} users (including superuser)'))
        
        if not options['keep_levels']:
            levels_count = Level.objects.count()
            Level.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {levels_count} levels'))
        else:
            self.stdout.write(self.style.WARNING('○ Kept levels data'))
        
        if not options['keep_nations']:
            nations_count = Nation.objects.count()
            Nation.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {nations_count} nations'))
        else:
            self.stdout.write(self.style.WARNING('○ Kept nations data'))
        
        self.reset_sequences()
        
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.SUCCESS('CLEANUP COMPLETED!'))
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(f'Remaining levels: {Level.objects.count()}')
        self.stdout.write(f'Remaining nations: {Nation.objects.count()}')
        self.stdout.write(f'Remaining users: {User.objects.count()}')
        self.stdout.write(f'Remaining crewmen: {Crewman.objects.count()}')
        self.stdout.write(f'Remaining tanks: {Tank.objects.count()}')
        self.stdout.write(f'Remaining battles: {BattleRecord.objects.count()}')
        self.stdout.write('='*50)
    
    def reset_sequences(self):
        """Сброс автоинкрементов для SQLite"""
        if connection.vendor == 'sqlite':
            tables = [
                m._meta.db_table
                for m in (BattleRecord, Tank, Crewman, Level, Nation)
            ]
            placeholders = ', '.join(['%s'] * len(tables))
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
                        tables,
                    )
                self.stdout.write(self.style.SUCCESS('✓ Reset auto-increment sequences'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Не удалось сбросить автоинкременты: {e}'))