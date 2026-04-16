<script setup>
import { onBeforeMount, ref, watch, inject } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";

const userStore = useUserStore();
const tanksStore = useTanksStore();
const openImageViewer = inject('openImageViewer');

const { userInfo } = storeToRefs(userStore);
const { myTanks, levels } = storeToRefs(tanksStore);

const selectedTankId = ref(null);
const selectedBattleLevelId = ref(null);
const availableLevels = ref([]);
const showResultModal = ref(false);
const battleResult = ref(null);
const isProcessing = ref(false);
const countdown = ref(0);
let countdownInterval = null;

onBeforeMount(async () => {
    await tanksStore.fetchMyTanks();
    await tanksStore.fetchLevels();
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

watch(selectedTankId, () => {
    selectedBattleLevelId.value = null;
    updateAvailableLevels();
});

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

async function startBattle() {
    if (!selectedTankId.value || !selectedBattleLevelId.value) return;
    isProcessing.value = true;
    countdown.value = 5;
    countdownInterval = setInterval(() => {
        if (countdown.value > 0) countdown.value--;
        else clearInterval(countdownInterval);
    }, 1000);
    try {
        const result = await tanksStore.startBattle(selectedTankId.value, selectedBattleLevelId.value);
        clearInterval(countdownInterval);
        battleResult.value = result;
        showResultModal.value = true;
    } catch (error) {
        clearInterval(countdownInterval);
        alert(error.message || 'Ошибка при начале боя');
    } finally {
        isProcessing.value = false;
        countdown.value = 0;
    }
}

function closeResultModal() {
    showResultModal.value = false;
    battleResult.value = null;
    // Не очищаем selectedTankId и selectedBattleLevelId, чтобы можно было повторить
}

async function repeatBattle() {
    // Закрываем модалку и сразу начинаем новый бой с теми же параметрами
    showResultModal.value = false;
    await startBattle();
}

function getTankImage(tankId) {
    const tank = myTanks.value.find(t => t.id === tankId);
    return tank?.picture || null;
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
            <div class="row">
                <div class="col-md-6">
                    <div class="custom-card">
                        <div class="custom-card-header">Начать сражение</div>
                        <div class="custom-card-body">
                            <div v-if="myTanks.filter(t => !t.is_in_battle).length === 0">
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
                                        <option :value="tank.id" v-for="tank in myTanks" :key="tank.id" :disabled="tank.is_in_battle">
                                            {{ tank.name }} (Lv.{{ tanksStore.getLevelInfo(tank.level)?.level_number }})
                                            {{ tank.is_in_battle ? '- В БОЮ' : '' }}
                                        </option>
                                    </select>
                                </div>
                                <div class="form-group" v-if="selectedTankId">
                                    <label>Выберите уровень сражения</label>
                                    <select class="custom-form-select" v-model="selectedBattleLevelId" required>
                                        <option :value="null" disabled>Выберите уровень</option>
                                        <option :value="level.id" v-for="level in availableLevels" :key="level.id">
                                            {{ level.level_number }} уровень (Награда: {{ level.battle_reward }}💰)
                                            (Шанс: {{ getWinChance(selectedTankId, level.id) }}%)
                                        </option>
                                    </select>
                                </div>
                                <div v-if="selectedTankId && selectedBattleLevelId" class="alert-custom-info">
                                    <strong>Шанс победы:</strong> {{ getWinChance(selectedTankId, selectedBattleLevelId) }}%
                                </div>
                                <button type="submit" class="btn-custom-danger w-100" :disabled="isProcessing">
                                    {{ isProcessing ? `Бой идёт... ${countdown}с` : 'Начать бой!' }}
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
                                    <span :class="tank.is_in_battle ? 'text-danger' : 'text-success'">
                                        {{ tank.is_in_battle ? 'В бою' : 'Готов' }}
                                    </span>
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

    <!-- Модалка результата с кнопкой Повтор -->
    <div v-if="showResultModal && battleResult" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header" :class="battleResult.result === 'victory' ? 'bg-success' : 'bg-danger'">
                    <h5>{{ battleResult.result === 'victory' ? 'ПОБЕДА!' : 'ПОРАЖЕНИЕ!' }}</h5>
                    <button class="close-btn" @click="closeResultModal">&times;</button>
                </div>
                <div class="custom-modal-body text-center">
                    <h3>{{ battleResult.result === 'victory' ? '🎉 Вы победили! 🎉' : '💥 Вы проиграли... 💥' }}</h3>
                    <p><strong>Получено кредитов:</strong> {{ battleResult.reward_earned }} 💰</p>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-warning" @click="repeatBattle">Повтор</button>
                    <button class="btn-custom-primary" @click="closeResultModal">Закрыть</button>
                </div>
            </div>
        </div>
    </div>
</template>