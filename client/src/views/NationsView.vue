<script setup>
import { onBeforeMount, ref } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";
import { showSuccess, showError } from '@/utils/notifications';

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { nations } = storeToRefs(tanksStore);

const newNation = ref({ name: '', flag: null });
const editNation = ref(null);
const showEditModal = ref(false);
const flagFile = ref(null);
const flagInput = ref(null);
const editFlagFile = ref(null);

onBeforeMount(async () => {
    await tanksStore.fetchNations();
});

function extractError(err, fallback) {
    const data = err.response?.data;
    return data?.error || data?.name?.[0] || data?.flag?.[0] || data?.detail || fallback;
}

async function createNation() {
    const name = newNation.value.name.trim();
    if (!name) {
        showError('Ошибка', 'Введите название нации');
        return;
    }
    const formData = new FormData();
    formData.append('name', name);
    if (flagFile.value) formData.append('flag', flagFile.value);
    try {
        await tanksStore.createNation(formData);
        newNation.value = { name: '', flag: null };
        flagFile.value = null;
        if (flagInput.value) flagInput.value.value = '';
    } catch (err) {
        showError('Ошибка', extractError(err, 'Не удалось создать нацию'));
    }
}
async function updateNation() {
    if (!editNation.value) return;
    const name = editNation.value.name.trim();
    if (!name) {
        showError('Ошибка', 'Введите название нации');
        return;
    }
    const formData = new FormData();
    formData.append('name', name);
    if (editFlagFile.value) formData.append('flag', editFlagFile.value);
    try {
        await tanksStore.updateNation(editNation.value.id, formData);
        showEditModal.value = false;
        editNation.value = null;
        editFlagFile.value = null;
    } catch (err) {
        showError('Ошибка', extractError(err, 'Не удалось сохранить нацию'));
    }
}
async function deleteNation(id) {
    if (confirm('Удалить нацию?')) {
        try {
            await tanksStore.deleteNation(id);
            showSuccess('Удалено', 'Нация удалена');
        } catch (err) {
            showError('Ошибка', extractError(err, 'Не удалось удалить нацию'));
        }
    }
}
function openEditModal(nation) {
    editNation.value = { ...nation };
    showEditModal.value = true;
}
function onFlagChange(event) { flagFile.value = event.target.files[0]; }
function onEditFlagChange(event) { editFlagFile.value = event.target.files[0]; }
</script>

<template>
    <div class="custom-container">
        <div v-if="userInfo && userInfo.is_authenticated && userInfo.is_staff">
            <div class="custom-card mb-4">
                <div class="custom-card-header bg-danger">Управление нациями</div>
                <div class="custom-card-body" v-if="userInfo.second">
                    <h5>Добавить нацию</h5>
                    <div class="row">
                        <div class="col-md-5">
                            <input type="text" class="custom-form-control" v-model="newNation.name" placeholder="Название нации">
                        </div>
                        <div class="col-md-5">
                            <input type="file" class="custom-form-control" ref="flagInput" @change="onFlagChange" accept="image/*">
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
                        <input type="file" class="custom-form-control" @change="onEditFlagChange" accept="image/*">
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