<script setup>
import { onBeforeMount, onMounted, ref, watch, inject, onUnmounted, computed } from 'vue';
import axios from 'axios';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const openImageViewer = inject('openImageViewer');
const selectedUserData = ref(null);

const { userInfo } = storeToRefs(userStore);
const { myTanks, levels, nations, allCrewmen } = storeToRefs(tanksStore);

const selectedTank = ref(null);
const showUpgradeModal = ref(false);
const showSellModal = ref(false);
const showEditModal = ref(false);
const editingTank = ref(null);
const editForm = ref({ name: '', nation: null });
const editPictureFile = ref(null);
const editPicturePreview = ref(null);
const loading = ref(false);

// Количество танков в ангаре без учёта фильтров
const garageCount = ref(0);

const filters = ref({ nation: null, level: null, is_in_battle: null });
const selectedUserId = ref(null);

// Администратор с 2FA смотрит чужой ангар
const viewingOtherUser = computed(() =>
    !!(selectedUserId.value && userInfo.value.is_staff && userInfo.value.second)
);

const battleTimers = ref({});
let timerInterval = null;

// Один запрос за активными боями + по одному /remaining-time/ на бой.
// Дальше обратный отсчёт идёт локально, без запросов к серверу.
async function syncBattleTimers() {
    const tanksInBattle = myTanks.value?.filter(t => t.is_in_battle) || [];
    if (tanksInBattle.length === 0) {
        battleTimers.value = {};
        return;
    }

    const { data } = await axios.get('/api/battles/', { params: { result: 'pending' } });
    const next = {};
    for (const tank of tanksInBattle) {
        const activeBattle = data.find(b => b.tank === tank.id);
        if (activeBattle) {
            const timeData = await tanksStore.getBattleRemainingTime(activeBattle.id);
            next[tank.id] = { remaining: timeData.remaining };
        }
    }
    battleTimers.value = next;
}

function startTimerUpdates() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        for (const id in battleTimers.value) {
            const timer = battleTimers.value[id];
            if (timer.remaining > 0) timer.remaining -= 1;
        }
    }, 1000);
}

function battleStatusText(tank) {
    const seconds = battleTimers.value[tank.id]?.remaining;
    return seconds > 0 ? `${seconds} сек` : 'В бою';
}

watch(() => userInfo.value.is_authenticated, async (newVal, oldVal) => {
    if (newVal === true && oldVal === false) {
        await loadAllData();
    }
});

async function loadTanks() {
    if (viewingOtherUser.value) {
        await tanksStore.fetchTanksByUser(selectedUserId.value);
        selectedUserData.value = allCrewmen.value.find(c => c.id === selectedUserId.value) || null;
    } else {
        await tanksStore.fetchMyTanks();
        selectedUserData.value = null;
    }
    garageCount.value = myTanks.value?.length || 0;
}

function hasActiveFilters() {
    return !!(filters.value.nation || filters.value.level || filters.value.is_in_battle !== null);
}

async function applyFilters() {
    if (!hasActiveFilters()) {
        await loadTanks();
        return;
    }
    const params = {
        owner__id: viewingOtherUser.value ? selectedUserId.value : userInfo.value.crewman_id,
    };
    if (filters.value.nation) params.nation__name = filters.value.nation;
    if (filters.value.level) params.level__level_number = filters.value.level;
    if (filters.value.is_in_battle !== null) params.is_in_battle = filters.value.is_in_battle;
    await tanksStore.fetchTanks(params);
}

async function reloadTanks() {
    await loadTanks();
    if (hasActiveFilters()) {
        await applyFilters();
    }
}

watch(filters, () => applyFilters(), { deep: true });

// Выбранный ангар запоминается до конца сессии браузера
watch(selectedUserId, async (newVal) => {
    if (newVal) {
        sessionStorage.setItem('selectedUserId', newVal);
    } else {
        sessionStorage.removeItem('selectedUserId');
    }
    await reloadTanks();
});

async function loadAllData() {
    loading.value = true;
    try {
        await userStore.checkLogin();
        await loadTanks();
        if (!levels.value.length) {
            await tanksStore.fetchLevels();
        }
        if (!nations.value.length) {
            await tanksStore.fetchNations();
        }
        if (userInfo.value.is_staff && userInfo.value.second && !allCrewmen.value.length) {
            await tanksStore.fetchAllCrewmen();
        }
        await syncBattleTimers();
        startTimerUpdates();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    } finally {
        loading.value = false;
    }
}

onBeforeMount(() => {
    const savedUserId = sessionStorage.getItem('selectedUserId');
    if (savedUserId) {
        selectedUserId.value = parseInt(savedUserId);
    }
});

onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
});

onMounted(() => {
    loadAllData();
});

function openUpgradeModal(tank) {
    selectedTank.value = tank;
    showUpgradeModal.value = true;
}

function openSellModal(tank) {
    selectedTank.value = tank;
    showSellModal.value = true;
}

// Общая часть подтверждения улучшения и продажи
async function confirmAction(modalFlag, action, successTitle, successText, errorText) {
    if (!selectedTank.value) return;
    modalFlag.value = false;
    const tank = selectedTank.value;
    selectedTank.value = null;
    try {
        await action(tank.id);
        await loadAllData();
        showSuccess(successTitle, successText);
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, errorText));
    }
}

function confirmUpgrade() {
    return confirmAction(showUpgradeModal, tanksStore.upgradeTank, 'Улучшение!', 'Танк успешно улучшен', 'Ошибка улучшения');
}

function confirmSell() {
    return confirmAction(showSellModal, tanksStore.sellTank, 'Продажа!', 'Танк успешно продан', 'Ошибка продажи');
}

async function expandGarage() {
    try {
        await userStore.expandGarage();
        await loadAllData();
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Не удалось расширить ангар'));
    }
}

function openEditModal(tank) {
    editingTank.value = tank;
    editForm.value = {
        name: tank.name,
        nation: tank.nation
    };
    editPictureFile.value = null;
    editPicturePreview.value = null;
    showEditModal.value = true;
}

function onEditPictureChange(event) {
    const file = event.target.files[0];
    if (file) {
        editPictureFile.value = file;
        editPicturePreview.value = URL.createObjectURL(file);
    }
}

async function saveEdit() {
    const formData = new FormData();
    formData.append('name', editForm.value.name);
    formData.append('nation', editForm.value.nation);
    if (editPictureFile.value) {
        formData.append('picture', editPictureFile.value);
    }
    try {
        await axios.put(`/api/tanks/${editingTank.value.id}/`, formData);
        showEditModal.value = false;
        editingTank.value = null;
        await loadAllData();
        showSuccess('Сохранено!', 'Танк обновлён');
    } catch (error) {
        showError('Ошибка', getErrorMessage(error, 'Не удалось сохранить танк'));
    }
}

async function refreshCrewmenList() {
    if (userInfo.value.is_staff && userInfo.value.second) {
        await tanksStore.fetchAllCrewmen();
    }
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_authenticated">
            <div v-if="loading" class="text-center p-5">
                <div class="alert-custom-info">Загрузка данных...</div>
            </div>
            
            <div v-else>
                <div v-if="userInfo.is_staff && userInfo.second" class="mb-3">
                    <label class="text-white">Посмотреть ангар пользователя:</label>
                    <select class="custom-form-select" v-model="selectedUserId" @focus="refreshCrewmenList">
                        <option :value="null">-- Мой ангар --</option>
                        <option v-for="c in allCrewmen" :key="c.id" :value="c.id">
                            {{ c.username }} (танков: {{ c.tanks_count }})
                        </option>
                    </select>
                </div>

                <div class="row mb-3">
                    <div class="col-md-4">
                        <select class="custom-form-select" v-model="filters.nation">
                            <option :value="null">Все нации</option>
                            <option v-for="n in nations" :key="n.id" :value="n.name">{{ n.name }}</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <select class="custom-form-select" v-model="filters.level">
                            <option :value="null">Все уровни</option>
                            <option v-for="l in levels" :key="l.id" :value="l.level_number">{{ l.level_number }}</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <select class="custom-form-select" v-model="filters.is_in_battle">
                            <option :value="null">Любой статус</option>
                            <option :value="true">В бою</option>
                            <option :value="false">Не в бою</option>
                        </select>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="custom-card bg-primary text-white">
                            <div class="custom-card-body">
                                <h5>Кредиты</h5>
                                <h2>{{ viewingOtherUser && selectedUserData ? selectedUserData.credits : (userInfo.credits || 0) }} 💰</h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="custom-card bg-success text-white">
                            <div class="custom-card-body">
                                <h5>Ангар</h5>
                                <h2>{{ garageCount }} / {{ viewingOtherUser && selectedUserData ? selectedUserData.garage_slots : userInfo.garage_slots }}</h2>
                                <button v-if="!viewingOtherUser && garageCount >= userInfo.garage_slots" 
                                        class="btn-custom-warning btn-sm mt-2" @click="expandGarage">
                                    + Место (500💰)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h2 class="tanks-title">{{ viewingOtherUser && selectedUserData ? `Танки игрока ${selectedUserData.username}` : 'Мои танки' }}</h2>
                </div>

                <div class="row" v-if="myTanks && myTanks.length > 0">
                    <div class="col-md-4" v-for="tank in myTanks" :key="tank.id">
                        <div class="tank-card" :class="{ 'opacity-50': tank.is_in_battle }">
                            <div class="tank-image" @click="openImageViewer(tank.picture)" v-if="tank.picture">
                                <img :src="tank.picture" class="tank-img">
                            </div>
                            <div class="tank-image-placeholder" v-else>
                                🚀
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center mt-2">
                                <h5>{{ tank.name }}</h5>
                                <span class="badge" style="background:#dc3545; padding:4px 8px; border-radius:20px;">Lv.{{ tank.level_number }}</span>
                            </div>
                            
                            <p><strong>Нация: </strong> 
                                <img v-if="tanksStore.getNationInfo(tank.nation)?.flag" 
                                     :src="tanksStore.getNationInfo(tank.nation).flag" 
                                     style="width: 24px; height: 16px; object-fit: cover; margin-left: 5px;">
                                {{ tank.nation_name }}
                            </p>
                            <p><strong>Урон/мин: </strong> {{ tank.dpm }}</p>
                            <p><strong>Статус: </strong> 
                                <span v-if="tank.is_in_battle" class="text-warning">⚔️ В бою</span>
                                <span v-else class="text-success">
                                    Готов
                                </span>
                            </p>
                            
                            <div class="d-flex gap-2 mt-3" v-if="!tank.is_in_battle">
                                <button v-if="tank.upgrade_cost" 
                                        class="btn-action btn-upgrade" 
                                        @click="openUpgradeModal(tank)"
                                        title="Улучшить">⬆️</button>
                                <button class="btn-action btn-sell" 
                                        @click="openSellModal(tank)"
                                        title="Продать">💰</button>
                                <button class="btn-action btn-edit" 
                                        @click="openEditModal(tank)"
                                        title="Редактировать">✏️</button>
                            </div>
                            <div v-else class="alert-custom-warning text-center mt-2">
                                ⚔️ {{ battleStatusText(tank) }}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div v-else class="alert-custom-info text-center">
                    <p>У вас пока нет танков</p>
                    <router-link to="/tanks" class="btn-custom-danger">Создать танк</router-link>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">
            Пожалуйста, авторизуйтесь
        </div>
    </div>

    <!-- Модалка Улучшения -->
    <div v-if="showUpgradeModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Улучшить танк</h5>
                    <button class="close-btn" @click="showUpgradeModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <p>Вы уверены, что хотите улучшить <strong>{{ selectedTank?.name }}</strong>?</p>
                    <p>Стоимость: <strong>{{ selectedTank?.upgrade_cost }} 💰</strong></p>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showUpgradeModal = false">Отмена</button>
                    <button class="btn-custom-warning" @click="confirmUpgrade">Улучшить</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модалка Продажи -->
    <div v-if="showSellModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Продать танк</h5>
                    <button class="close-btn" @click="showSellModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <p>Вы уверены, что хотите продать <strong>{{ selectedTank?.name }}</strong>?</p>
                    <p>Вы получите: <strong>{{ selectedTank?.sell_price }} 💰</strong></p>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showSellModal = false">Отмена</button>
                    <button class="btn-custom-danger" @click="confirmSell">Продать</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модалка Редактирования -->
    <div v-if="showEditModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Редактировать танк</h5>
                    <button class="close-btn" @click="showEditModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <div class="form-group">
                        <label>Название</label>
                        <input type="text" class="custom-form-control" v-model="editForm.name">
                    </div>
                    <div class="form-group">
                        <label>Нация</label>
                        <select class="custom-form-select" v-model="editForm.nation">
                            <option v-for="n in nations" :key="n.id" :value="n.id">{{ n.name }}</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Новое изображение</label>
                        <input type="file" class="custom-form-control" @change="onEditPictureChange" accept="image/*">
                        <img v-if="editPicturePreview" :src="editPicturePreview" style="max-width: 200px; margin-top: 10px;">
                    </div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showEditModal = false">Отмена</button>
                    <button class="btn-custom-primary" @click="saveEdit">Сохранить</button>
                </div>
            </div>
        </div>
    </div>
</template>