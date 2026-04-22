<script setup>
import { onBeforeMount, ref, watch, computed } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { battles, myTanks, levels } = storeToRefs(tanksStore);

const filterResult = ref('all');
const filteredBattles = ref([]);

const totalWins = computed(() => {
    return battles.value.filter(b => b.result === 'victory').length;
});

const totalDefeats = computed(() => {
    return battles.value.filter(b => b.result === 'defeat').length;
});

const totalEarned = computed(() => {
    return battles.value.reduce((sum, b) => sum + (b.reward_earned || 0), 0);
});

const winRate = computed(() => {
    if (battles.value.length === 0) return 0;
    return Math.round((totalWins.value / battles.value.length) * 100);
});

onBeforeMount(async () => {
    await tanksStore.fetchBattles();
    await tanksStore.fetchMyTanks();
    await tanksStore.fetchLevels();
});

function getTankName(tankId) {
    const tank = myTanks.value.find(t => t.id === tankId);
    return tank ? tank.name : 'Неизвестный танк';
}

function getLevelNumber(levelId) {
    const level = tanksStore.getLevelInfo(levelId);
    return level ? level.level_number : '?';
}

function getResultText(result) {
    switch(result) {
        case 'victory': return '🏆 Победа';
        case 'defeat': return '💀 Поражение';
        default: return '⏳ Ожидание';
    }
}

function getResultClass(result) {
    switch(result) {
        case 'victory': return 'text-success';
        case 'defeat': return 'text-danger';
        default: return 'text-warning';
    }
}

function formatDate(dateString) {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
}

function applyFilters() {
    let result = [...battles.value];
    if (filterResult.value !== 'all') {
        result = result.filter(b => b.result === filterResult.value);
    }
    filteredBattles.value = result;
}

watch([battles, filterResult], () => applyFilters(), { deep: true, immediate: true });
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="custom-card bg-primary text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalWins }}</h3>
                            <p>Побед</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-danger text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalDefeats }}</h3>
                            <p>Поражений</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-success text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalEarned }}</h3>
                            <p>Заработано</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-warning text-dark text-center">
                        <div class="custom-card-body">
                            <h3>{{ winRate }}%</h3>
                            <p>Winrate</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="custom-card mb-3">
                <div class="custom-card-body">
                    <div class="form-group">
                        <label>Фильтр по результату</label>
                        <select class="custom-form-select" v-model="filterResult">
                            <option value="all">Все бои</option>
                            <option value="victory">Только победы</option>
                            <option value="defeat">Только поражения</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="custom-card">
                <div class="custom-card-header bg-danger">История боёв</div>
                <div class="custom-card-body">
                    <div v-if="filteredBattles.length === 0" class="alert-custom-info text-center">
                        <p>История боёв пуста</p>
                        <router-link to="/battles" class="btn-custom-danger">Начать первый бой!</router-link>
                    </div>
                    <div v-for="battle in filteredBattles" :key="battle.id" class="border-bottom pb-3 mb-3">
                        <div class="d-flex justify-content-between">
                            <div><strong>{{ getTankName(battle.tank) }}</strong> vs Уровень {{ getLevelNumber(battle.battle_level) }}</div>
                            <div :class="getResultClass(battle.result)"><strong>{{ getResultText(battle.result) }}</strong></div>
                        </div>
                        <div class="d-flex justify-content-between mt-1">
                            <small>💰 {{ battle.reward_earned || 0 }} кредитов</small>
                            <small>📅 {{ formatDate(battle.started_at) }}</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Пожалуйста, авторизуйтесь</div>
    </div>
</template>