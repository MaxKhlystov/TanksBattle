<script setup>
import { onBeforeMount, ref, watch, inject, onUnmounted, computed } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const openImageViewer = inject('openImageViewer');

const { userInfo } = storeToRefs(userStore);
const { myTanks, levels, battles } = storeToRefs(tanksStore);

const selectedTankId = ref(null);
const selectedBattleLevelId = ref(null);
// Флаг «идёт запрос»: блокирует кнопку запуска и не даёт restoreBattlesState
// пересоздавать таймеры, пока startBattleFor ещё не закончил работу
const isProcessing = ref(false);

const activeBattles = ref({});      // tankId -> { remaining, battleId, intervalId }
const pendingResults = ref({});     // tankId -> { battleId } — бой окончен, награду можно забрать
const claiming = ref({});

const showResultModalFlag = ref(false);
const currentBattleResult = ref(null);

function clearAllTimers() {
    Object.values(activeBattles.value).forEach(battle => clearInterval(battle.intervalId));
}

// Локальный обратный отсчёт боя; по окончании танк переходит в «Забрать награду»
function startCountdown(tankId, battleId, seconds) {
    const intervalId = setInterval(() => {
        const battle = activeBattles.value[tankId];
        if (!battle) {
            clearInterval(intervalId);
            return;
        }
        battle.remaining -= 1;
        if (battle.remaining <= 0) {
            clearInterval(intervalId);
            delete activeBattles.value[tankId];
            pendingResults.value[tankId] = { battleId };
            tanksStore.fetchMyTanks();
        }
    }, 1000);
    activeBattles.value[tankId] = { remaining: seconds, battleId, intervalId };
}

// Восстанавливает таймеры по активным боям с сервера (после перезагрузки страницы)
function restoreBattlesState() {
    if (isProcessing.value) return;
    clearAllTimers();
    activeBattles.value = {};
    pendingResults.value = {};

    for (const tank of myTanks.value) {
        const battle = battles.value.find(b => b.tank === tank.id && b.result === 'pending');
        if (!battle) continue;

        const duration = tank.level_number;  // длительность боя = уровень танка (секунды)
        const elapsed = (Date.now() - new Date(battle.started_at)) / 1000;
        if (elapsed >= duration) {
            pendingResults.value[tank.id] = { battleId: battle.id };
        } else {
            startCountdown(tank.id, battle.id, Math.ceil(duration - elapsed));
        }
    }
}

const isSelectedTankInBattle = computed(() => {
    if (!selectedTankId.value) return false;
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (!tank) return false;
    return tank.is_in_battle || !!activeBattles.value[selectedTankId.value];
});

const selectedTankRemainingTime = computed(() => {
    return activeBattles.value[selectedTankId.value]?.remaining ?? null;
});

// Уровни боя, доступные выбранному танку: его уровень и соседние (±1), как на сервере
const availableLevels = computed(() => {
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (!tank) return [];
    return levels.value.filter(level => Math.abs(level.level_number - tank.level_number) <= 1);
});

// Запуск боя из формы: танк и уровень берутся из выбранных значений
async function startBattle() {
    if (!selectedTankId.value || !selectedBattleLevelId.value) {
        showError('Ошибка', 'Выберите танк и уровень боя');
        return;
    }
    await startBattleFor(selectedTankId.value, selectedBattleLevelId.value);
}

// Запуск боя для конкретного танка (используется и формой, и кнопкой «Повтор»)
async function startBattleFor(tankId, battleLevelId) {
    const tank = myTanks.value.find(t => t.id === tankId);
    if (!tank) {
        showError('Ошибка', 'Танк не найден');
        return;
    }
    if (tank.is_in_battle || activeBattles.value[tankId]) {
        showError('Ошибка', 'Этот танк уже участвует в бою! Дождитесь окончания.');
        return;
    }

    isProcessing.value = true;
    try {
        const battle = await tanksStore.startBattle(tankId, battleLevelId);
        startCountdown(tankId, battle.id, battle.battle_duration);
        await tanksStore.fetchMyTanks();
        await tanksStore.fetchBattles();
        showSuccess('Бой начался!', 'Танк отправлен в бой');
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Не удалось начать бой'));
    } finally {
        isProcessing.value = false;
    }
}

async function claimReward(tankId) {
    const pending = pendingResults.value[tankId];
    if (!pending || claiming.value[tankId]) return;
    claiming.value[tankId] = true;

    try {
        currentBattleResult.value = await tanksStore.claimBattle(pending.battleId);
        showResultModalFlag.value = true;
        delete pendingResults.value[tankId];
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Не удалось получить результат боя'));
        await tanksStore.fetchMyTanks();
        await tanksStore.fetchBattles();
    } finally {
        delete claiming.value[tankId];
    }
}

async function cancelBattle(tankId) {
    const battle = activeBattles.value[tankId];
    if (!battle) return;

    clearInterval(battle.intervalId);
    delete activeBattles.value[tankId];
    try {
        await tanksStore.cancelBattle(battle.battleId);
        showSuccess('Бой отменён', 'Танк вернулся в ангар');
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Не удалось отменить бой'));
        await tanksStore.fetchMyTanks();
    }
}

function closeResultModal() {
    showResultModalFlag.value = false;
    currentBattleResult.value = null;
}

onUnmounted(clearAllTimers);

function getWinChance(tankId, battleLevelId) {
    const tank = myTanks.value.find(t => t.id === tankId);
    const battleLevel = tanksStore.getLevelInfo(battleLevelId);
    if (!tank || !battleLevel) return 0;
    // те же правила, что в claim_battle на сервере
    if (battleLevel.level_number < tank.level_number) return 100;
    if (battleLevel.level_number === tank.level_number) return 75;
    return 25;
}

// «Повтор»: тот же танк и тот же уровень боя, что в только что завершённом бою
function repeatBattle() {
    const result = currentBattleResult.value;
    showResultModalFlag.value = false;
    if (result?.tank && result?.battle_level) {
        startBattleFor(result.tank, result.battle_level);
    }
}

watch(selectedTankId, () => {
    selectedBattleLevelId.value = null;
});

watch([myTanks, battles], restoreBattlesState, { deep: true });

onBeforeMount(async () => {
    await tanksStore.fetchMyTanks();
    await tanksStore.fetchLevels();
    await tanksStore.fetchBattles();
    restoreBattlesState();
});
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_authenticated">
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
                                            {{ tank.name }} (Lv.{{ tank.level_number }})
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
                                        <span class="badge" style="background:#dc3545; margin-left:8px;">Lv.{{ tank.level_number }}</span>
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
                                        <button class="btn-custom-success btn-sm" :disabled="claiming[tank.id]" @click="claimReward(tank.id)">
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