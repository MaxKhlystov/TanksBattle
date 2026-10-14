<script setup>
import { onBeforeMount, ref } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError, showConfirm, getErrorMessage } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { nations } = storeToRefs(tanksStore);

const newNationName = ref('');
const flagFile = ref(null);
const flagInput = ref(null);
const editNation = ref(null);
const editFlagFile = ref(null);
const showEditModal = ref(false);

onBeforeMount(async () => {
    await tanksStore.fetchNations();
});

// Общая подготовка данных формы для создания и изменения нации
function buildNationForm(rawName, file) {
    const name = rawName.trim();
    if (!name) {
        showError('Ошибка', 'Введите название нации');
        return null;
    }
    const formData = new FormData();
    formData.append('name', name);
    if (file) formData.append('flag', file);
    return formData;
}

async function createNation() {
    const formData = buildNationForm(newNationName.value, flagFile.value);
    if (!formData) return;
    try {
        await tanksStore.createNation(formData);
        newNationName.value = '';
        flagFile.value = null;
        if (flagInput.value) flagInput.value.value = '';
        showSuccess('Добавлено', 'Нация создана');
    } catch (err) {
        showError('Ошибка', getErrorMessage(err, 'Не удалось создать нацию'));
    }
}

async function updateNation() {
    if (!editNation.value) return;
    const formData = buildNationForm(editNation.value.name, editFlagFile.value);
    if (!formData) return;
    try {
        await tanksStore.updateNation(editNation.value.id, formData);
        showEditModal.value = false;
        editNation.value = null;
        editFlagFile.value = null;
        showSuccess('Сохранено', 'Нация обновлена');
    } catch (err) {
        showError('Ошибка', getErrorMessage(err, 'Не удалось сохранить нацию'));
    }
}

async function deleteNation(id) {
    if (!(await showConfirm('Удалить нацию?'))) return;
    try {
        await tanksStore.deleteNation(id);
        showSuccess('Удалено', 'Нация удалена');
    } catch (err) {
        showError('Ошибка', getErrorMessage(err, 'Не удалось удалить нацию'));
    }
}

function openEditModal(nation) {
    editNation.value = { ...nation };
    editFlagFile.value = null;
    showEditModal.value = true;
}
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo.is_authenticated && userInfo.is_staff">
            <div class="custom-card mb-4">
                <div class="custom-card-header bg-danger">Управление нациями</div>
                <div class="custom-card-body" v-if="userInfo.second">
                    <h5>Добавить нацию</h5>
                    <div class="row">
                        <div class="col-md-5">
                            <input type="text" class="custom-form-control" v-model="newNationName" placeholder="Название нации">
                        </div>
                        <div class="col-md-5">
                            <input type="file" class="custom-form-control" ref="flagInput" @change="flagFile = $event.target.files[0]" accept="image/*">
                        </div>
                        <div class="col-md-2">
                            <button class="btn-custom-success w-100" @click="createNation">Добавить</button>
                        </div>
                    </div>
                </div>
                <div class="custom-card-body" v-else>
                    <div class="alert-custom-warning mb-0">
                        Для добавления, изменения и удаления наций требуется двухфакторная аутентификация
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-3 mb-3" v-for="nation in nations" :key="nation.id">
                    <div class="custom-card text-center">
                        <div class="custom-card-body">
                            <div class="mb-2">
                                <img v-if="nation.flag" :src="nation.flag" style="max-width: 100px; max-height: 50px;">
                                <div v-else style="font-size: 40px;">🚩</div>
                            </div>
                            <h5>{{ nation.name }}</h5>
                            <button class="btn-custom-warning btn-sm me-1"  v-if="userInfo.second" @click="openEditModal(nation)">✏️</button>
                            <button class="btn-custom-danger btn-sm"  v-if="userInfo.second" @click="deleteNation(nation.id)">🗑️</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="alert-custom-warning">Доступ только для администраторов</div>
    </div>

    <div v-if="showEditModal" class="modal-overlay">
        <div class="modal-dialog-custom">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5>Редактировать нацию</h5>
                    <button class="close-btn" @click="showEditModal = false">&times;</button>
                </div>
                <div class="custom-modal-body">
                    <div class="form-group">
                        <label>Название</label>
                        <input type="text" class="custom-form-control" v-model="editNation.name">
                    </div>
                    <div v-if="editNation?.flag" class="form-group">
                        <label>Текущий флаг</label><br>
                        <img :src="editNation.flag" style="max-width: 100px;">
                    </div>
                    <div class="form-group">
                        <label>Новый флаг (оставьте пустым, чтобы не менять)</label>
                        <input type="file" class="custom-form-control" @change="editFlagFile = $event.target.files[0]" accept="image/*">
                    </div>
                </div>
                <div class="custom-modal-footer">
                    <button class="btn-custom-secondary" @click="showEditModal = false">Отмена</button>
                    <button class="btn-custom-primary" @click="updateNation">Сохранить</button>
                </div>
            </div>
        </div>
    </div>
</template>