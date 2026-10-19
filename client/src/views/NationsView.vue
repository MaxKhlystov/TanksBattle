<script setup>
import { onBeforeMount, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { nations } = storeToRefs(tanksStore);

const nationToAdd = ref({ name: '' });
const nationToEdit = ref({});
const flagRef = ref(null);
const editFlagRef = ref(null);

onBeforeMount(async () => {
    await tanksStore.fetchNations();
});

async function onNationAdd() {
    const formData = new FormData();
    formData.append('name', nationToAdd.value.name);
    if (flagRef.value.files[0]) {
        formData.append('flag', flagRef.value.files[0]);
    }
    try {
        await tanksStore.createNation(formData);
    } catch (error) {
        alert('Ошибка: ' + JSON.stringify(error.response.data));
    }
    nationToAdd.value = { name: '' };
    flagRef.value.value = '';
}

function onEditClick(nation) {
    nationToEdit.value = { ...nation };
}

async function onNationUpdate() {
    const formData = new FormData();
    formData.append('name', nationToEdit.value.name);
    if (editFlagRef.value.files[0]) {
        formData.append('flag', editFlagRef.value.files[0]);
    }
    try {
        await tanksStore.updateNation(nationToEdit.value.id, formData);
    } catch (error) {
        alert('Ошибка: ' + JSON.stringify(error.response.data));
    }
    editFlagRef.value.value = '';
}

async function onRemoveClick(nation) {
    if (!confirm(`Удалить нацию ${nation.name}?`)) {
        return;
    }
    try {
        await tanksStore.deleteNation(nation.id);
    } catch (error) {
        alert(error.response.data.error);
    }
}
</script>

<template>
    <div class="card mb-3" v-if="userInfo.second">
        <div class="card-header">Добавить нацию</div>
        <div class="card-body">
            <form @submit.prevent.stop="onNationAdd" class="row">
                <div class="col">
                    <input type="text" class="form-control" v-model="nationToAdd.name" placeholder="Название" required>
                </div>
                <div class="col">
                    <input type="file" class="form-control" ref="flagRef" accept="image/*">
                </div>
                <div class="col-auto">
                    <button type="submit" class="btn btn-success">Добавить</button>
                </div>
            </form>
        </div>
    </div>
    <div class="alert alert-warning" v-else>Для изменения наций нужна двухфакторная аутентификация</div>

    <div class="card">
        <div class="card-header">Нации</div>
        <div class="card-body">
            <table class="table">
                <thead>
                    <tr>
                        <th>Флаг</th>
                        <th>Название</th>
                        <th v-if="userInfo.second"></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="nation in nations" :key="nation.id">
                        <td>
                            <img v-if="nation.flag" :src="nation.flag" height="30">
                            <span v-else>нет флага</span>
                        </td>
                        <td>{{ nation.name }}</td>
                        <td v-if="userInfo.second">
                            <button class="btn btn-secondary btn-sm me-2" data-bs-toggle="modal" data-bs-target="#editNationModal"
                                    @click="onEditClick(nation)">Изменить</button>
                            <button class="btn btn-danger btn-sm" @click="onRemoveClick(nation)">Удалить</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="modal" id="editNationModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Изменить нацию</h5>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Название</label>
                        <input type="text" class="form-control" v-model="nationToEdit.name">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Новый флаг</label>
                        <input type="file" class="form-control" ref="editFlagRef" accept="image/*">
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button class="btn btn-primary" data-bs-dismiss="modal" @click="onNationUpdate">Сохранить</button>
                </div>
            </div>
        </div>
    </div>
</template>
