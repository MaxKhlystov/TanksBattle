<script setup>
import { onBeforeMount, ref, watch } from 'vue';
import axios from 'axios';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { battles, myTanks, levels, allCrewmen, fetchAllCrewmen } = storeToRefs(tanksStore);

const filterResult = ref('all');
const filteredBattles = ref([]);
const selectedUserId = ref(null);

onBeforeMount(async () => {
    await loadBattles();
    await tanksStore.fetchMyTanks();
    await tanksStore.fetchLevels();
    if (userInfo.value.is_staff && userInfo.value.second) {
        await tanksStore.fetchAllCrewmen();
    }
});

async function loadBattles() {
    if (selectedUserId.value && userInfo.value.is_staff && userInfo.value.second) {
        const response = await axios.get(`/api/battles/?crewman=${selectedUserId.value}`);
        battles.value = response.data;
    } else {
        await tanksStore.fetchBattles();
    }
}

watch(selectedUserId, async () => {
    await loadBattles();
    applyFilters();
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

const totalWins = () => battles.value.filter(b => b.result === 'victory').length;
const totalDefeats = () => battles.value.filter(b => b.result === 'defeat').length;
const totalEarned = () => battles.value.reduce((sum, b) => sum + b.reward_earned, 0);
const winRate = () => {
    if (battles.value.length === 0) return 0;
    return Math.round((totalWins() / battles.value.length) * 100);
};
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
            <!-- Выбор пользователя для суперюзера с 2FA -->
            <div v-if="userInfo.is_staff && userInfo.second" class="mb-3">
                <label>Посмотреть историю боёв пользователя:</label>
                <select class="custom-form-select" v-model="selectedUserId">
                    <option :value="null">-- Моя история --</option>
                    <option v-for="c in allCrewmen" :key="c.id" :value="c.id">
                        {{ c.username }}
                    </option>
                </select>
            </div>

            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="custom-card bg-primary text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalWins() }}</h3>
                            <p>Побед</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-danger text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalDefeats() }}</h3>
                            <p>Поражений</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-success text-white text-center">
                        <div class="custom-card-body">
                            <h3>{{ totalEarned() }}</h3>
                            <p>Заработано</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="custom-card bg-warning text-dark text-center">
                        <div class="custom-card-body">
                            <h3>{{ winRate() }}%</h3>
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
                            <small>💰 {{ battle.reward_earned }} кредитов</small>
                            <small>📅 {{ formatDate(battle.started_at) }}</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Пожалуйста, авторизуйтесь</div>
    </div>
</template>