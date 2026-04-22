from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection

from tanks.models import Nation, Level, Crewman, Tank, BattleRecord


class Command(BaseCommand):
    help = 'Clean all database tables (except superuser and basic data)'

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
            '--keep-superuser',
            action='store_true',
            help='Keep superuser account (default: True)',
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Full clean - delete ALL data including levels and nations',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('='*50))
        self.stdout.write(self.style.WARNING('STARTING DATABASE CLEANUP'))
        self.stdout.write(self.style.WARNING('='*50))
        
        battles_count = BattleRecord.objects.count()
        BattleRecord.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {battles_count} battle records'))
        
        tanks_count = Tank.objects.count()
        Tank.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {tanks_count} tanks'))
        
        if options.get('keep_superuser', True):
            users_to_delete = User.objects.filter(is_superuser=False, is_staff=False)
            users_count = users_to_delete.count()
            
            for user in users_to_delete:
                Crewman.objects.filter(user=user).delete()
            
            users_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {users_count} regular users'))
        else:
            users_count = User.objects.count()
            Crewman.objects.all().delete()
            User.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {users_count} users (including superuser)'))
        
        if options.get('full') or not options.get('keep_levels'):
            levels_count = Level.objects.count()
            Level.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {levels_count} levels'))
        else:
            self.stdout.write(self.style.WARNING('○ Kept levels data'))
        
        if options.get('full') or not options.get('keep_nations'):
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
            with connection.cursor() as cursor:
                tables = ['tanks_battle_record', 'tanks_tank', 'tanks_crewman', 'tanks_level', 'tanks_nation']
                for table in tables:
                    try:
                        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}';")
                    except:
                        pass
            self.stdout.write(self.style.SUCCESS('✓ Reset auto-increment sequences'))