<script setup>
import { onBeforeMount, ref, watch, inject, onUnmounted, computed } from 'vue';
import axios from 'axios';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const openImageViewer = inject('openImageViewer');

const { userInfo } = storeToRefs(userStore);
const { myTanks, levels, battles } = storeToRefs(tanksStore); // +++ добавили battles

const selectedTankId = ref(null);
const selectedBattleLevelId = ref(null);
const availableLevels = ref([]);
const isProcessing = ref(false);

const activeBattles = ref({});      
const pendingResults = ref({});     

const showResultModalFlag = ref(false);
const currentBattleResult = ref(null);

function getBattleByTank(tankId) {
    return battles.value.find(b => b.tank === tankId && b.result === 'pending');
}

async function restoreBattlesState() {
    if (isProcessing.value) return;   
    isProcessing.value = true;
    try {
        Object.values(activeBattles.value).forEach(battle => {
            if (battle.intervalId) clearInterval(battle.intervalId);
        });
        activeBattles.value = {};
        pendingResults.value = {};

        for (const tank of myTanks.value) {
            const battle = getBattleByTank(tank.id);
            if (!battle) continue;

            const tankLevel = tanksStore.getLevelInfo(tank.level);
            const duration = tankLevel?.level_number || 5;
            const startedAt = new Date(battle.started_at);
            const now = new Date();
            const elapsed = (now - startedAt) / 1000;
            
            if (elapsed >= duration) {
                pendingResults.value[tank.id] = { battleId: battle.id };
            } else {
                const remaining = Math.ceil(duration - elapsed);
                const intervalId = setInterval(() => {
                    if (activeBattles.value[tank.id]) {
                        const newRemaining = activeBattles.value[tank.id].remaining - 1;
                        if (newRemaining <= 0) {
                            clearInterval(intervalId);
                            delete activeBattles.value[tank.id];
                            pendingResults.value[tank.id] = { battleId: battle.id };
                            tanksStore.fetchMyTanks();
                        } else {
                            activeBattles.value[tank.id].remaining = newRemaining;
                        }
                    }
                }, 1000);
                
                activeBattles.value[tank.id] = {
                    remaining: remaining,
                    total: duration,
                    battleId: battle.id,
                    intervalId: intervalId
                };
            }
        }
    } catch (error) {
        showError('Ошибка', error.response?.data?.error || 'Не удалось загрузить ангар');
    } finally {
        isProcessing.value = false;
    }
}

const isSelectedTankInBattle = computed(() => {
    if (!selectedTankId.value) return false;
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (!tank) return false;
    return tank.is_in_battle || !!activeBattles.value[selectedTankId.value];
});

const selectedTankRemainingTime = computed(() => {
    if (!selectedTankId.value) return null;
    const battle = activeBattles.value[selectedTankId.value];
    return battle ? battle.remaining : null;
});

async function startBattle() {
    if (!selectedTankId.value || !selectedBattleLevelId.value) {
        showError('Ошибка', 'Выберите танк и уровень боя');
        return;
    }
    if (isSelectedTankInBattle.value) {
        showError('Ошибка', 'Этот танк уже участвует в бою! Дождитесь окончания.');
        return;
    }
    
    const tankId = selectedTankId.value;
    const battleLevelId = selectedBattleLevelId.value;
    const tank = myTanks.value.find(t => t.id === tankId);
    const tankLevel = tanksStore.getLevelInfo(tank.level);
    const duration = tankLevel?.level_number || 5;
    
    isProcessing.value = true;
    
    try {
        const result = await tanksStore.startBattle(tankId, battleLevelId);
        
        let remaining = duration;
        const timerId = setInterval(() => {
            remaining--;
            if (activeBattles.value[tankId]) {
                activeBattles.value[tankId].remaining = remaining;
            }
            if (remaining <= 0) {
                clearInterval(timerId);
                if (activeBattles.value[tankId]) {
                    const battleId = activeBattles.value[tankId].battleId;
                    delete activeBattles.value[tankId];
                    pendingResults.value[tankId] = { battleId };
                    tanksStore.fetchMyTanks();
                }
            }
        }, 1000);
        
        activeBattles.value[tankId] = {
            remaining: duration,
            total: duration,
            battleId: result.battleId,
            intervalId: timerId
        };
        
        await tanksStore.fetchMyTanks();
        await tanksStore.fetchBattles(); 
        showSuccess('Бой начался!', 'Танк отправлен в бой');
        
    } catch (error) {
        showError('Ошибка', error.response?.data?.error || 'Не удалось начать бой');
    } finally {
        isProcessing.value = false;
    }
}

async function claimReward(tankId) {
    const pending = pendingResults.value[tankId];
    if (!pending) return;
    
    try {
        const result = await tanksStore.claimBattle(pending.battleId);
        showResultModal(result);
        delete pendingResults.value[tankId];
        await tanksStore.fetchMyTanks();
        await tanksStore.fetchBattles();
    } catch (error) {
        showError('Ошибка', error.response?.data?.error || 'Не удалось получить результат боя');
    }
}

async function cancelBattle(tankId) {
    const battle = activeBattles.value[tankId];
    if (!battle) return;
    
    clearInterval(battle.intervalId);
    
    try {
        await axios.post(`/api/battles/${battle.battleId}/cancel/`);
        delete activeBattles.value[tankId];
        await tanksStore.fetchMyTanks();
        await tanksStore.fetchBattles();
        showSuccess('Бой отменён', 'Танк вернулся в ангар');
    } catch (error) {
        showError('Ошибка', 'Не удалось отменить бой');
        await tanksStore.fetchMyTanks();
        delete activeBattles.value[tankId];
    }
}

function showResultModal(result) {
    currentBattleResult.value = result;
    showResultModalFlag.value = true;
}

function closeResultModal() {
    showResultModalFlag.value = false;
    currentBattleResult.value = null;
}

onUnmounted(() => {
    Object.values(activeBattles.value).forEach(battle => {
        if (battle.intervalId) clearInterval(battle.intervalId);
    });
});

function updateAvailableLevels() {
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (!tank || !levels.value.length) {
        availableLevels.value = [];
        return;
    }
    const tankLevel = tanksStore.getLevelInfo(tank.level);
    if (!tankLevel) return;
    const tankLevelNum = tankLevel.level_number;
    availableLevels.value = levels.value.filter(level => {
        const diff = Math.abs(level.level_number - tankLevelNum);
        return diff <= 1;
    });
}

function getWinChance(tankId, battleLevelId) {
    const tank = myTanks.value.find(t => t.id === tankId);
    const battleLevel = tanksStore.getLevelInfo(battleLevelId);
    if (!tank || !battleLevel) return 0;
    const tankLevel = tanksStore.getLevelInfo(tank.level);
    if (!tankLevel) return 0;
    const tankLevelNum = tankLevel.level_number;
    const battleLevelNum = battleLevel.level_number;
    if (battleLevelNum < tankLevelNum) return 100;
    if (battleLevelNum === tankLevelNum) return 75;
    return 25;
}

function repeatBattle() {
    showResultModalFlag.value = false;
    if (selectedTankId.value && selectedBattleLevelId.value) {
        startBattle();
    }
}

watch(selectedTankId, () => {
    selectedBattleLevelId.value = null;
    updateAvailableLevels();
});

watch([myTanks, battles], async () => {
    await restoreBattlesState();
}, { deep: true });

onBeforeMount(async () => {
    await tanksStore.fetchMyTanks();
    await tanksStore.fetchLevels();
    await tanksStore.fetchBattles(); 
    await restoreBattlesState();     
});
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
            <div class="row">
                <div class="col-md-6">
                    <div class="custom-card">
                        <div class="custom-card-header">Начать сражение</div>
                        <div class="custom-card-body">
                            <div v-if="myTanks.filter(t => !t.is_in_battle && !activeBattles[t.id]).length === 0">
                                <div class="alert-custom-warning">
                                    У вас нет свободных танков для боя
                                </div>
                                <router-link to="/tanks" class="btn-custom-primary">Создать танк</router-link>
                            </div>
                            <form v-else @submit.prevent="startBattle">
                                <div class="form-group">
                                    <label>Выберите танк</label>
                                    <select class="custom-form-select" v-model="selectedTankId" required>
                                        <option :value="null" disabled>Выберите танк</option>
                                        <option :value="tank.id" v-for="tank in myTanks" :key="tank.id" 
                                            :disabled="tank.is_in_battle || activeBattles[tank.id]">
                                            {{ tank.name }} (Lv.{{ tanksStore.getLevelInfo(tank.level)?.level_number }})
                                            {{ tank.is_in_battle || activeBattles[tank.id] ? '- В БОЮ' : '' }}
                                        </option>
                                    </select>
                                    <small v-if="selectedTankId && isSelectedTankInBattle" class="text-warning">
                                        ⚠️ Этот танк уже в бою! (осталось {{ selectedTankRemainingTime }} сек)
                                    </small>
                                </div>
                                <div class="form-group" v-if="selectedTankId && !isSelectedTankInBattle">
                                    <label>Выберите уровень сражения</label>
                                    <select class="custom-form-select" v-model="selectedBattleLevelId" required>
                                        <option :value="null" disabled>Выберите уровень</option>
                                        <option :value="level.id" v-for="level in availableLevels" :key="level.id">
                                            {{ level.level_number }} уровень (Награда: {{ level.battle_reward }}💰)
                                            (Шанс: {{ getWinChance(selectedTankId, level.id) }}%)
                                        </option>
                                    </select>
                                </div>
                                <div v-if="selectedTankId && selectedBattleLevelId && !isSelectedTankInBattle" class="alert-custom-info">
                                    <strong>Шанс победы:</strong> {{ getWinChance(selectedTankId, selectedBattleLevelId) }}%
                                </div>
                                <button type="submit" class="btn-custom-danger w-100" 
                                        :disabled="isProcessing || !selectedTankId || !selectedBattleLevelId || isSelectedTankInBattle">
                                    {{ isProcessing ? 'Отправка...' : 'Начать бой!' }}
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="custom-card">
                        <div class="custom-card-header bg-success">Ваши танки</div>
                        <div class="custom-card-body">
                            <div v-for="tank in myTanks" :key="tank.id" class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
                                <div class="d-flex align-items-center">
                                    <img v-if="tank.picture" 
                                         :src="tank.picture" 
                                         @click="openImageViewer(tank.picture)"
                                         style="width: 40px; height: 40px; object-fit: cover; border-radius: 8px; margin-right: 10px; cursor: pointer;">
                                    <div v-else style="width: 40px; height: 40px; background: #555; border-radius: 8px; margin-right: 10px;"></div>
                                    <div>
                                        <strong>{{ tank.name }}</strong>
                                        <span class="badge" style="background:#dc3545; margin-left:8px;">Lv.{{ tanksStore.getLevelInfo(tank.level)?.level_number }}</span>
                                    </div>
                                </div>
                                <div>
                                    <!-- Танк в активном бою (таймер) -->
                                    <div v-if="activeBattles[tank.id]" class="d-flex gap-2 align-items-center">
                                        <button class="btn-custom-warning btn-sm" @click="cancelBattle(tank.id)">
                                            Отменить
                                        </button>
                                        <span class="text-warning">
                                            ⚔️ {{ activeBattles[tank.id].remaining }} сек
                                        </span>
                                    </div>
                                    <div v-else-if="pendingResults[tank.id]" class="d-flex gap-2 align-items-center">
                                        <button class="btn-custom-success btn-sm" @click="claimReward(tank.id)">
                                            Забрать
                                        </button>
                                    </div>
                                    <div v-else-if="!tank.is_in_battle">
                                        <span class="text-success">
                                            Готов
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div v-if="myTanks.length === 0" class="alert-custom-warning">У вас нет танков</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Пожалуйста, авторизуйтесь</div>
    </div>

    <div v-if="showResultModalFlag && currentBattleResult" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header" :class="currentBattleResult.result === 'victory' ? 'bg-success' : 'bg-danger'">
                    <h5>{{ currentBattleResult.result === 'victory' ? 'ПОБЕДА!' : 'ПОРАЖЕНИЕ!' }}</h5>
                    <button class="close-btn" @click="closeResultModal">&times;</button>
                </div>
                <div class="custom-modal-body text-center">
                    <h3>{{ currentBattleResult.result === 'victory' ? '🎉 Вы победили! 🎉' : '💥 Вы проиграли... 💥' }}</h3>
                    <p><strong>Получено кредитов:</strong> {{ currentBattleResult.reward_earned }} 💰</p>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-warning" @click="repeatBattle">Повтор</button>
                    <button class="btn-custom-primary" @click="closeResultModal">Закрыть</button>
                </div>
            </div>
        </div>
    </div>
</template>