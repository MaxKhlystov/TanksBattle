<script setup>
import { computed, onBeforeMount, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { nations, levels } = storeToRefs(tanksStore);

const tankToAdd = ref({ name: '', nation: null, level: null });
const pictureRef = ref(null);

const cost = computed(() => {
    const level = tanksStore.getLevelInfo(tankToAdd.value.level);
    return level ? level.creation_cost : 0;
});

onBeforeMount(async () => {
    await tanksStore.fetchNations();
    await tanksStore.fetchLevels();
});

async function onTankAdd() {
    const formData = new FormData();
    formData.append('name', tankToAdd.value.name);
    formData.append('nation', tankToAdd.value.nation);
    formData.append('level', tankToAdd.value.level);
    if (pictureRef.value.files[0]) {
        formData.append('picture', pictureRef.value.files[0]);
    }
    try {
        await tanksStore.createTank(formData);
    } catch (error) {
        alert(error.response.data.error);
        return;
    }
    await userStore.checkLogin();
    tankToAdd.value = { name: '', nation: null, level: null };
    pictureRef.value.value = '';
    alert('Танк создан');
}
</script>

<template>
    <div class="card">
        <div class="card-header">Создать новый танк</div>
        <div class="card-body">
            <form @submit.prevent.stop="onTankAdd">
                <div class="mb-3">
                    <label class="form-label">Название танка</label>
                    <input type="text" class="form-control" v-model="tankToAdd.name" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Нация</label>
                    <select class="form-select" v-model="tankToAdd.nation" required>
                        <option v-for="n in nations" :key="n.id" :value="n.id">{{ n.name }}</option>
                    </select>
                </div>
                <div class="mb-3">
                    <label class="form-label">Уровень</label>
                    <select class="form-select" v-model="tankToAdd.level" required>
                        <option v-for="l in levels" :key="l.id" :value="l.id">
                            {{ l.level_number }} уровень ({{ l.creation_cost }} кредитов)
                        </option>
                    </select>
                </div>
                <div class="mb-3">
                    <label class="form-label">Изображение</label>
                    <input type="file" class="form-control" ref="pictureRef" accept="image/*">
                </div>
                <p>Стоимость: {{ cost }} кредитов. У вас: {{ userInfo.credits }} кредитов.</p>
                <button type="submit" class="btn btn-primary">Создать танк</button>
            </form>
        </div>
    </div>
</template>
