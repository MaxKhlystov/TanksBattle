from django.contrib import admin
from .models import Nation, Level, Crewman, Tank, BattleRecord

@admin.register(Nation)
class NationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'flag']
    list_display_links = ['name']
    search_fields = ['name']
    fields = ['name', 'flag']
    
@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ['id', 'level_number', 'creation_cost', 'upgrade_to_next_cost', 'battle_reward']
    list_display_links = ['level_number']
    search_fields = ['level_number']
    readonly_fields = ['creation_cost', 'upgrade_to_next_cost', 'battle_reward']
    
    def creation_cost(self, obj):
        return obj.creation_cost
    creation_cost.short_description = "Стоимость создания"
    
    def upgrade_to_next_cost(self, obj):
        return obj.upgrade_to_next_cost if obj.upgrade_to_next_cost is not None else "-"
    upgrade_to_next_cost.short_description = "Стоимость повышения до след. уровня"
    
    def battle_reward(self, obj):
        return obj.battle_reward
    battle_reward.short_description = "Награда за бой"

@admin.register(Crewman)
class CrewmanAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'credits', 'garage_slots', 'available_garage_slots', 'created_at']
    list_display_links = ['user']
    list_editable = ['credits', 'garage_slots']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'available_garage_slots']
    
    def available_garage_slots(self, obj):
        return obj.available_garage_slots()
    available_garage_slots.short_description = "Свободных мест"

@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'owner', 'nation', 'level', 'dpm', 'is_in_battle', 'created_at']
    list_display_links = ['name']
    list_filter = ['nation', 'level', 'is_in_battle', 'owner']
    search_fields = ['name', 'owner__user__username']
    readonly_fields = ['dpm', 'upgrade_cost', 'sell_price', 'created_at']
    actions = ['free_tanks_from_battle']
    
    def dpm(self, obj):
        return obj.dpm
    dpm.short_description = "Урон в минуту"
    
    def upgrade_cost(self, obj):
        return obj.upgrade_cost if obj.upgrade_cost is not None else "-"
    upgrade_cost.short_description = "Стоимость повышения"
    
    def sell_price(self, obj):
        return obj.sell_price
    sell_price.short_description = "Цена продажи"
    
    def free_tanks_from_battle(self, request, queryset):
        updated = queryset.update(is_in_battle=False)
        self.message_user(request, f"{updated} танков освобождено из боя")
    free_tanks_from_battle.short_description = "Освободить выбранные танки из боя"

@admin.register(BattleRecord)
class BattleRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'tank', 'crewman', 'battle_level', 'result', 'reward_earned', 'started_at', 'finished_at']
    list_display_links = ['tank']
    list_filter = ['result', 'battle_level', 'started_at']
    search_fields = ['tank__name', 'crewman__user__username']
    readonly_fields = ['started_at', 'finished_at', 'reward_earned']
    list_editable = ['result']
    actions = ['process_victory', 'process_defeat']
    
    def process_victory(self, request, queryset):
        count = 0
        for battle in queryset:
            if battle.result == 'pending':
                battle.process_battle_result(True)
                count += 1
        self.message_user(request, f"{count} боёв отмечено как победа")
    process_victory.short_description = "Отметить выбранные бои как ПОБЕДУ"
    
    def process_defeat(self, request, queryset):
        count = 0
        for battle in queryset:
            if battle.result == 'pending':
                battle.process_battle_result(False)
                count += 1
        self.message_user(request, f"{count} боёв отмечено как поражение")
    process_defeat.short_description = "Отметить выбранные бои как ПОРАЖЕНИЕ"