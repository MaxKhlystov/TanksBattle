from rest_framework import serializers
from .models import Nation, Level, Crewman, Tank, BattleRecord

class NationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nation
        fields = ['id', 'name', 'flag']

class LevelSerializer(serializers.ModelSerializer):
    creation_cost = serializers.IntegerField(read_only=True)
    upgrade_to_next_cost = serializers.IntegerField(read_only=True)
    battle_reward = serializers.IntegerField(read_only=True)

    class Meta:
        model = Level
        fields = ['id', 'level_number', 'creation_cost', 'upgrade_to_next_cost', 'battle_reward']

class CrewmanSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = Crewman
        fields = ['id', 'username', 'credits', 'garage_slots', 'available_slots', 'created_at']

    def get_available_slots(self, obj):
        return obj.available_garage_slots()

class TankSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.user.username', read_only=True)
    level_number = serializers.IntegerField(source='level.level_number', read_only=True)
    nation_name = serializers.CharField(source='nation.name', read_only=True)
    upgrade_cost = serializers.IntegerField(read_only=True)
    sell_price = serializers.IntegerField(read_only=True)
    dpm = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tank
        fields = ['id', 'name', 'owner', 'owner_name', 'nation', 'nation_name',
                  'level', 'level_number', 'is_in_battle', 'dpm', 'upgrade_cost',
                  'sell_price', 'created_at', 'picture']
        read_only_fields = ['owner', 'is_in_battle', 'created_at', 'dpm', 'upgrade_cost', 'sell_price']

    def create(self, validated_data):
        if 'request' in self.context:
            validated_data['owner'] = self.context['request'].user.crewman
        return super().create(validated_data)

class BattleRecordSerializer(serializers.ModelSerializer):
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    crewman_name = serializers.CharField(source='crewman.user.username', read_only=True)
    battle_level_number = serializers.IntegerField(source='battle_level.level_number', read_only=True)

    class Meta:
        model = BattleRecord
        fields = ['id', 'tank', 'tank_name', 'crewman', 'crewman_name',
                  'battle_level', 'battle_level_number', 'result', 'reward_earned',
                  'started_at', 'finished_at']
        read_only_fields = ['crewman', 'result', 'reward_earned', 'started_at', 'finished_at']