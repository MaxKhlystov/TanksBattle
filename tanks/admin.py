from django.contrib import admin
from .models import Nation, Level, Crewman, Tank, BattleRecord
from .permissions import is_admin

@admin.register(Nation)
class NationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'flag']
    search_fields = ['name']

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ['id', 'level_number', 'creation_cost', 'battle_reward']

@admin.register(Crewman)
class CrewmanAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'credits', 'garage_slots', 'created_at']
    search_fields = ['user__username']

@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'owner', 'nation', 'level', 'is_in_battle', 'created_at']
    list_filter = ['nation', 'level', 'is_in_battle']
    search_fields = ['name', 'owner__user__username']

@admin.register(BattleRecord)
class BattleRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'tank', 'crewman', 'battle_level', 'result', 'reward_earned', 'started_at']
    list_filter = ['result', 'battle_level']

def has_permission(request):
    return is_admin(request)

admin.site.has_permission = has_permission