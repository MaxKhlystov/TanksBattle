<script setup>
import { onBeforeMount, ref } from 'vue';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';
import { storeToRefs } from "pinia";

const userStore = useUserStore();
const tanksStore = useTanksStore();

const { userInfo } = storeToRefs(userStore);
const { nations } = storeToRefs(tanksStore);

const newNation = ref({ name: '', flag: null });
const editNation = ref(null);
const showEditModal = ref(false);
const flagFile = ref(null);
const editFlagFile = ref(null);

onBeforeMount(async () => {
    await tanksStore.fetchNations();
});

async function createNation() {
    const formData = new FormData();
    formData.append('name', newNation.value.name);
    if (flagFile.value) formData.append('flag', flagFile.value);
    await tanksStore.createNation(formData);
    newNation.value = { name: '', flag: null };
    flagFile.value = null;
}
async function updateNation() {
    if (editNation.value) {
        const formData = new FormData();
        formData.append('name', editNation.value.name);
        if (editFlagFile.value) formData.append('flag', editFlagFile.value);
        await tanksStore.updateNation(editNation.value.id, formData);
        showEditModal.value = false;
        editNation.value = null;
        editFlagFile.value = null;
    }
}
async function deleteNation(id) {
    if (confirm('Удалить нацию?')) {
        await tanksStore.deleteNation(id);
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
                            <input type="file" class="custom-form-control" @change="onFlagChange" accept="image/*">
                        </div>
                        <div class="col-md-2">
                            <button class="btn-custom-success w-100" @click="createNation">Добавить</button>
                        </div>
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
        <div v-else-if="userInfo && userInfo.is_authenticated && userInfo.is_staff && !userInfo.second" class="alert-custom-warning">
            Для доступа к этой странице требуется двухфакторная аутентификация
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