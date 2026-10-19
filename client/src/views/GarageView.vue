<script setup>
import { onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import ImageViewer from '@/views/ImageViewer.vue';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { myTanks, nations, levels, allCrewmen } = storeToRefs(tanksStore);

const filters = ref({ nation: null, level: null, is_in_battle: null });
const selectedUserId = ref(null);
const tankToEdit = ref({});
const editPictureRef = ref(null);
const currentImage = ref('');

function isAdmin() {
    return userInfo.value.is_staff && userInfo.value.second;
}

function selectedUser() {
    return allCrewmen.value.find(c => c.id === selectedUserId.value);
}

async function loadTanks() {
    const params = { owner__id: selectedUserId.value || userInfo.value.crewman_id };
    if (filters.value.nation) params.nation__name = filters.value.nation;
    if (filters.value.level) params.level__level_number = filters.value.level;
    if (filters.value.is_in_battle !== null) params.is_in_battle = filters.value.is_in_battle;
    await tanksStore.fetchTanks(params);
}

async function loadAll() {
    await tanksStore.fetchNations();
    await tanksStore.fetchLevels();
    if (isAdmin()) {
        await tanksStore.fetchAllCrewmen();
    }
    await loadTanks();
}

onMounted(() => {
    if (userInfo.value.is_authenticated) {
        loadAll();
    }
});

watch(() => userInfo.value.is_authenticated, (value) => {
    if (value) {
        loadAll();
    }
});

watch(filters, loadTanks, { deep: true });
watch(selectedUserId, loadTanks);

async function onUpgrade(tank) {
    if (!confirm(`Улучшить танк ${tank.name} за ${tank.upgrade_cost} кредитов?`)) {
        return;
    }
    try {
        await tanksStore.upgradeTank(tank.id);
    } catch (error) {
        alert(error.response.data.error);
    }
    await userStore.checkLogin();
    await loadTanks();
}

async function onSell(tank) {
    if (!confirm(`Продать танк ${tank.name} за ${tank.sell_price} кредитов?`)) {
        return;
    }
    try {
        await tanksStore.sellTank(tank.id);
    } catch (error) {
        alert(error.response.data.error);
    }
    await userStore.checkLogin();
    await loadTanks();
}

async function onExpandGarage() {
    try {
        await userStore.expandGarage();
    } catch (error) {
        alert(error.response.data.error);
    }
}

function onEditClick(tank) {
    tankToEdit.value = Object.assign({}, tank);
}

async function onUpdateTank() {
    const formData = new FormData();
    formData.append('name', tankToEdit.value.name);
    formData.append('nation', tankToEdit.value.nation);
    if (editPictureRef.value.files[0]) {
        formData.append('picture', editPictureRef.value.files[0]);
    }
    try {
        await axios.put(`/api/tanks/${tankToEdit.value.id}/`, formData);
    } catch (error) {
        alert('Ошибка: ' + JSON.stringify(error.response.data));
    }
    editPictureRef.value.value = '';
    await loadTanks();
}
</script>

<template>
    <div v-if="userInfo.is_authenticated">
        <div v-if="isAdmin()" class="mb-3">
            <label class="form-label text-white">Посмотреть ангар пользователя</label>
            <select class="form-select" v-model="selectedUserId">
                <option :value="null">Мой ангар</option>
                <option v-for="c in allCrewmen" :key="c.id" :value="c.id">
                    {{ c.username }} (танков: {{ c.tanks_count }})
                </option>
            </select>
        </div>

        <div class="card mb-3">
            <div class="card-body">
                <div v-if="selectedUser()">
                    Игрок: {{ selectedUser().username }}.
                    Кредиты: {{ selectedUser().credits }}.
                    Мест в ангаре: {{ selectedUser().garage_slots }}
                </div>
                <div v-else>
                    Кредиты: {{ userInfo.credits }}.
                    Мест в ангаре: {{ userInfo.garage_slots }}
                    <button class="btn btn-warning btn-sm ms-3" @click="onExpandGarage">Купить место за 500 кредитов</button>
                </div>
            </div>
        </div>

        <div class="row mb-3">
            <div class="col">
                <select class="form-select" v-model="filters.nation">
                    <option :value="null">Все нации</option>
                    <option v-for="n in nations" :key="n.id" :value="n.name">{{ n.name }}</option>
                </select>
            </div>
            <div class="col">
                <select class="form-select" v-model="filters.level">
                    <option :value="null">Все уровни</option>
                    <option v-for="l in levels" :key="l.id" :value="l.level_number">{{ l.level_number }}</option>
                </select>
            </div>
            <div class="col">
                <select class="form-select" v-model="filters.is_in_battle">
                    <option :value="null">Любой статус</option>
                    <option :value="true">В бою</option>
                    <option :value="false">Не в бою</option>
                </select>
            </div>
        </div>

        <div class="row">
            <div class="col-md-4 mb-3" v-for="tank in myTanks" :key="tank.id">
                <div class="card">
                    <img v-if="tank.picture" :src="tank.picture" class="card-img-top tank-img"
                         data-bs-toggle="modal" data-bs-target="#imageModal" @click="currentImage = tank.picture">
                    <div class="card-body">
                        <h5 class="card-title">{{ tank.name }}</h5>
                        <p class="mb-1">Уровень: {{ tank.level_number }}</p>
                        <p class="mb-1">Нация: {{ tank.nation_name }}</p>
                        <p class="mb-1">Урон в минуту: {{ tank.dpm }}</p>
                        <p>Статус: {{ tank.is_in_battle ? 'В бою' : 'Готов' }}</p>
                        <div v-if="!tank.is_in_battle">
                            <button v-if="tank.upgrade_cost" class="btn btn-primary btn-sm me-2" @click="onUpgrade(tank)">Улучшить</button>
                            <button class="btn btn-danger btn-sm me-2" @click="onSell(tank)">Продать</button>
                            <button class="btn btn-secondary btn-sm" data-bs-toggle="modal" data-bs-target="#editTankModal"
                                    @click="onEditClick(tank)">Изменить</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <p v-if="myTanks.length === 0" class="text-white">Танков нет</p>
    </div>
    <div v-else class="alert alert-warning">Пожалуйста, авторизуйтесь</div>

    <div class="modal" id="editTankModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Изменить танк</h5>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Название</label>
                        <input type="text" class="form-control" v-model="tankToEdit.name">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Нация</label>
                        <select class="form-select" v-model="tankToEdit.nation">
                            <option v-for="n in nations" :key="n.id" :value="n.id">{{ n.name }}</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Новое изображение</label>
                        <input type="file" class="form-control" ref="editPictureRef" accept="image/*">
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button class="btn btn-primary" data-bs-dismiss="modal" @click="onUpdateTank">Сохранить</button>
                </div>
            </div>
        </div>
    </div>

    <ImageViewer :src="currentImage" />
</template>
