<script setup>
import { onBeforeMount, onMounted, ref, watch, inject, onUnmounted } from 'vue';
import axios from 'axios';
import Cookies from 'js-cookie';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const openImageViewer = inject('openImageViewer');
const selectedUserData = ref(null); 

const { userInfo } = storeToRefs(userStore);
const { myTanks, levels, nations, allCrewmen, battles } = storeToRefs(tanksStore);
const { fetchAllCrewmen, fetchMyTanks, fetchLevels, fetchNations, upgradeTank, sellTank, fetchBattles } = tanksStore;

const selectedTank = ref(null);
const showUpgradeModal = ref(false);
const showSellModal = ref(false);
const showEditModal = ref(false);
const editingTank = ref(null);
const editForm = ref({ name: '', nation: null });
const editPictureFile = ref(null);
const editPicturePreview = ref(null);
const loading = ref(false);

const filters = ref({ nation: null, level: null, is_in_battle: null });
const selectedUserId = ref(null);

const battleTimers = ref({});
let timerInterval = null;

async function updateBattleTimers() {
    const tanksInBattle = myTanks.value?.filter(t => t.is_in_battle) || [];
    if (tanksInBattle.length === 0) return;
    
    await fetchBattles();
    const activeBattles = battles.value.filter(b => b.result === 'pending');
    
    for (const tank of tanksInBattle) {
        const activeBattle = activeBattles.find(b => b.tank === tank.id);
        if (activeBattle) {
            const timeData = await tanksStore.getBattleRemainingTime(activeBattle.id);
            battleTimers.value[tank.id] = {
                remaining: timeData.remaining,
                total: timeData.total_duration,
                battleId: activeBattle.id
            };
        } else if (tank.is_in_battle) {
            await fetchMyTanks();
        }
    }
}

function startTimerUpdates() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        if (myTanks.value?.some(t => t.is_in_battle)) {
            updateBattleTimers();
        }
    }, 1000);
}

function formatBattleTime(seconds) {
    if (seconds <= 0) return 'Завершается...';
    return `${seconds} сек`;
}

watch(selectedUserId, (newVal) => {
    if (newVal) {
        sessionStorage.setItem('selectedUserId', newVal);
    } else {
        sessionStorage.removeItem('selectedUserId');
    }
});

watch(() => userInfo.value.is_authenticated, async (newVal, oldVal) => {
    if (newVal === true && oldVal === false) {
        await loadAllData();
    }
});

async function loadTanks() {
    if (selectedUserId.value && userInfo.value.is_staff && userInfo.value.second) {
        await tanksStore.fetchTanksByUser(selectedUserId.value);
        const selectedUser = allCrewmen.value.find(c => c.id === selectedUserId.value);
        selectedUserData.value = selectedUser || null;
    } else {
        await tanksStore.fetchMyTanks();
        selectedUserData.value = null;
    }
}

async function applyFilters() {
    let url = '/api/tanks/';
    const params = new URLSearchParams();
    if (filters.value.nation) params.append('nation__name', filters.value.nation);
    if (filters.value.level) params.append('level__level_number', filters.value.level);
    if (filters.value.is_in_battle !== null) params.append('is_in_battle', filters.value.is_in_battle);
    if (selectedUserId.value && userInfo.value.is_staff && userInfo.value.second) {
        params.append('owner__id', selectedUserId.value);
    }
    
    if (params.toString()) {
        const response = await axios.get(url + '?' + params.toString());
        myTanks.value = response.data;
    } else {
        await loadTanks();
    }
}

watch(filters, () => applyFilters(), { deep: true });
watch(selectedUserId, async (newVal, oldVal) => {
    await loadTanks();
    await applyFilters();
});

async function loadAllData() {
    loading.value = true;
    try {
        await userStore.checkLogin();
        await loadTanks();
        if (!levels.value || levels.value.length === 0) {
            await fetchLevels();
        }
        if (!nations.value || nations.value.length === 0) {
            await fetchNations();
        }
        await fetchBattles();
        if (userInfo.value.is_staff && userInfo.value.second && (!allCrewmen.value || allCrewmen.value.length === 0)) {
            await fetchAllCrewmen();
        }
        await updateBattleTimers();
        startTimerUpdates();

        
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    }
}

onBeforeMount(() => {
    const savedUserId = sessionStorage.getItem('selectedUserId');
    if (savedUserId) {
        selectedUserId.value = parseInt(savedUserId);
    }
    axios.defaults.withCredentials = true;
    const csrfToken = Cookies.get("csrftoken");
    if (csrfToken) {
        axios.defaults.headers.common['X-CSRFToken'] = csrfToken;
    }
});

onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval);
});

onMounted(() => {
    loadAllData();
});

function getLevelNumber(levelId) {
    const level = tanksStore.getLevelInfo(levelId);
    return level ? level.level_number : '?';
}

function getNationName(nationId) {
    const nation = tanksStore.getNationInfo(nationId);
    return nation ? nation.name : '?';
}

function getUpgradeCost(tank) {
    const currentLevel = levels.value.find(l => l.level_number === tank.level_number);
    if (!currentLevel) {
        return null;
    }
    const cost = currentLevel.upgrade_to_next_cost;
    return cost || null;
}

async function handleUpgrade(tank) {
    selectedTank.value = tank;
    showUpgradeModal.value = true;
}

async function confirmUpgrade() {
    if (!selectedTank.value) return;
    
    showUpgradeModal.value = false;
    const tank = selectedTank.value;
    selectedTank.value = null;
    
    try {
        await upgradeTank(tank.id);
        await loadAllData();
        showSuccess('Улучшение!', 'Танк успешно улучшен');
    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Ошибка улучшения';
        showError('Ошибка', errorMsg);
    }
}

async function handleSell(tank) {
    selectedTank.value = tank;
    showSellModal.value = true;
}

async function confirmSell() {
    if (!selectedTank.value) return;
    
    showSellModal.value = false;
    const tank = selectedTank.value;
    selectedTank.value = null;
    
    try {
        await sellTank(tank.id);
        await loadAllData();
        showSuccess('Продажа!', 'Танк успешно продан');
    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Ошибка продажи';
        showError('Ошибка', errorMsg);
    }
}

async function expandGarage() {
    await userStore.expandGarage();
    await loadAllData();
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
    formData.append('level', editingTank.value.level);
    if (editPictureFile.value) {
        formData.append('picture', editPictureFile.value);
    }
    await axios.put(`/api/tanks/${editingTank.value.id}/`, formData);
    showEditModal.value = false;
    editingTank.value = null;
    await loadAllData();
    showSuccess('Сохранено!', 'Танк обновлён');
}

async function refreshCrewmenList() {
    if (userInfo.value.is_staff && userInfo.value.second) {
        await tanksStore.fetchAllCrewmen();
    }
}

</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated">
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
                                <h2>{{ selectedUserId && selectedUserData ? selectedUserData.credits : (userInfo.credits || 0) }} 💰</h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="custom-card bg-success text-white">
                            <div class="custom-card-body">
                                <h5>Ангар</h5>
                                <h2>{{ myTanks?.length || 0 }} / {{ selectedUserId && selectedUserData ? selectedUserData.garage_slots : (userInfo.garage_slots || 3) }}</h2>
                                <!-- Кнопка расширения ангара только для своего аккаунта -->
                                <button v-if="!selectedUserId && (myTanks?.length || 0) >= (userInfo.garage_slots || 3)" 
                                        class="btn-custom-warning btn-sm mt-2" @click="expandGarage">
                                    + Место (500💰)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h2 class="tanks-title">Мои танки</h2>
                </div>

                <div class="row" v-if="myTanks && myTanks.length > 0">
                    <div class="col-md-4" v-for="tank in myTanks" :key="tank.id">
                        <div class="tank-card" :class="{ 'opacity-50': tank.is_in_battle }">
                            <div class="tank-image" @click="openImageViewer(tank.picture)" v-if="tank.picture">
                                <img :src="tank.picture" class="tank-img">
                            </div>
                            <div class="tank-image-placeholder" @click="openImageViewer(tank.picture)" v-else>
                                🚀
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center mt-2">
                                <h5>{{ tank.name }}</h5>
                                <span class="badge" style="background:#dc3545; padding:4px 8px; border-radius:20px;">Lv.{{ getLevelNumber(tank.level) }}</span>
                            </div>
                            <p><strong>Нация: </strong> 
                                <img v-if="tanksStore.getNationInfo(tank.nation)?.flag" 
                                     :src="tanksStore.getNationInfo(tank.nation).flag" 
                                     style="width: 24px; height: 16px; object-fit: cover; margin-left: 5px;">
                                {{ getNationName(tank.nation) }}
                            </p>
                            <p><strong>Урон/мин: </strong> {{ tank.dpm }}</p>
                            <p><strong>Статус: </strong> 
                                <span v-if="tank.is_in_battle" class="text-warning">
                                    ⚔️ {{ battleTimers[tank.id]?.remaining > 0 ? formatBattleTime(battleTimers[tank.id].remaining) : 'В бою' }}
                                </span>
                                <span v-else class="text-success">
                                    Готов
                                </span>
                            </p>
                            <div class="d-flex gap-2 mt-3" v-if="!tank.is_in_battle">
                                <button v-if="getUpgradeCost(tank)" 
                                        class="btn-action btn-upgrade" 
                                        @click="handleUpgrade(tank)"
                                        title="Улучшить">⬆️</button>
                                <button class="btn-action btn-sell" 
                                        @click="handleSell(tank)"
                                        title="Продать">💰</button>
                                <button class="btn-action btn-edit" 
                                        @click="openEditModal(tank)"
                                        title="Редактировать">✏️</button>
                            </div>
                            <div v-else class="alert-custom-warning text-center mt-2">
                                ⚔️ {{ battleTimers[tank.id]?.remaining > 0 ? formatBattleTime(battleTimers[tank.id].remaining) : 'В бою' }}
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

    <div v-if="showUpgradeModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Улучшить танк</h5>
                    <button class="close-btn" @click="showUpgradeModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <p>Вы уверены, что хотите улучшить <strong>{{ selectedTank?.name }}</strong>?</p>
                    <p>Стоимость: <strong>{{ getUpgradeCost(selectedTank) }} 💰</strong></p>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showUpgradeModal = false">Отмена</button>
                    <button class="btn-custom-warning" @click="confirmUpgrade">Улучшить</button>
                </div>
            </div>
        </div>
    </div>

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