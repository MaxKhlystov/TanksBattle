<script setup>
import { computed, onBeforeMount, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { battles } = storeToRefs(tanksStore);

const filterResult = ref('all');

onBeforeMount(async () => {
    await tanksStore.fetchBattles({ crewman: userInfo.value.crewman_id });
});

const filteredBattles = computed(() => {
    if (filterResult.value === 'all') {
        return battles.value;
    }
    return battles.value.filter(b => b.result === filterResult.value);
});

const wins = computed(() => battles.value.filter(b => b.result === 'victory').length);
const defeats = computed(() => battles.value.filter(b => b.result === 'defeat').length);
const earned = computed(() => battles.value.reduce((sum, b) => sum + b.reward_earned, 0));
const winRate = computed(() => {
    if (wins.value + defeats.value === 0) {
        return 0;
    }
    return Math.round(wins.value / (wins.value + defeats.value) * 1000) / 10;
});

function resultText(result) {
    if (result === 'victory') return 'Победа';
    if (result === 'defeat') return 'Поражение';
    return 'Ожидание';
}
</script>

<template>
    <div class="card mb-3">
        <div class="card-body">
            Побед: {{ wins }}. Поражений: {{ defeats }}. Заработано: {{ earned }} кредитов. Процент побед: {{ winRate }}%
        </div>
    </div>

    <div class="mb-3">
        <select class="form-select" v-model="filterResult">
            <option value="all">Все бои</option>
            <option value="victory">Только победы</option>
            <option value="defeat">Только поражения</option>
        </select>
    </div>

    <div class="card">
        <div class="card-header">История боёв</div>
        <div class="card-body">
            <table class="table">
                <thead>
                    <tr>
                        <th>Танк</th>
                        <th>Уровень боя</th>
                        <th>Результат</th>
                        <th>Награда</th>
                        <th>Дата</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="battle in filteredBattles" :key="battle.id">
                        <td>{{ battle.tank_name }}</td>
                        <td>{{ battle.battle_level_number }}</td>
                        <td>{{ resultText(battle.result) }}</td>
                        <td>{{ battle.reward_earned }}</td>
                        <td>{{ new Date(battle.started_at).toLocaleString() }}</td>
                    </tr>
                </tbody>
            </table>
            <p v-if="filteredBattles.length === 0">Боёв нет</p>
        </div>
    </div>
</template>
