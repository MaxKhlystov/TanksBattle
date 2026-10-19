<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useUserStore } from '@/stores/user_store';
import { useTanksStore } from '@/stores/tanks_store';

const userStore = useUserStore();
const tanksStore = useTanksStore();
const { userInfo } = storeToRefs(userStore);
const { myTanks, levels, battles } = storeToRefs(tanksStore);

const selectedTankId = ref(null);
const selectedLevelId = ref(null);
const now = ref(Date.now());
let timer = null;

const freeTanks = computed(() => myTanks.value.filter(t => !t.is_in_battle));

const availableLevels = computed(() => {
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (!tank) {
        return [];
    }
    return levels.value.filter(l => Math.abs(l.level_number - tank.level_number) <= 1);
});

watch(selectedTankId, () => {
    selectedLevelId.value = null;
});

async function loadData() {
    await tanksStore.fetchTanks({ owner__id: userInfo.value.crewman_id });
    await tanksStore.fetchBattles({ result: 'pending', crewman: userInfo.value.crewman_id });
}

onMounted(async () => {
    await tanksStore.fetchLevels();
    await loadData();
    timer = setInterval(() => {
        now.value = Date.now();
    }, 1000);
});

onUnmounted(() => {
    clearInterval(timer);
});

function winChance(level) {
    const tank = myTanks.value.find(t => t.id === selectedTankId.value);
    if (level.level_number < tank.level_number) return 100;
    if (level.level_number === tank.level_number) return 75;
    return 25;
}

function activeBattle(tank) {
    return battles.value.find(b => b.tank === tank.id);
}

function secondsLeft(tank) {
    const battle = activeBattle(tank);
    const passed = (now.value - new Date(battle.started_at).getTime()) / 1000;
    return Math.ceil(tank.level_number - passed);
}

async function onStartBattle() {
    try {
        await tanksStore.startBattle(selectedTankId.value, selectedLevelId.value);
    } catch (error) {
        alert(error.response.data.error);
    }
    selectedTankId.value = null;
    await loadData();
}

async function onClaim(tank) {
    try {
        const battle = await tanksStore.claimBattle(activeBattle(tank).id);
        if (battle.result === 'victory') {
            alert(`Победа! Получено ${battle.reward_earned} кредитов`);
        } else {
            alert('Поражение');
        }
    } catch (error) {
        alert(error.response.data.error);
    }
    await userStore.checkLogin();
    await loadData();
}

async function onCancel(tank) {
    await tanksStore.cancelBattle(activeBattle(tank).id);
    await loadData();
}
</script>

<template>
    <div class="row">
        <div class="col-md-6">
            <div class="card mb-3">
                <div class="card-header">Начать сражение</div>
                <div class="card-body">
                    <form @submit.prevent.stop="onStartBattle">
                        <div class="mb-3">
                            <label class="form-label">Танк</label>
                            <select class="form-select" v-model="selectedTankId" required>
                                <option v-for="t in freeTanks" :key="t.id" :value="t.id">
                                    {{ t.name }} (уровень {{ t.level_number }})
                                </option>
                            </select>
                        </div>
                        <div class="mb-3" v-if="selectedTankId">
                            <label class="form-label">Уровень боя</label>
                            <select class="form-select" v-model="selectedLevelId" required>
                                <option v-for="l in availableLevels" :key="l.id" :value="l.id">
                                    {{ l.level_number }} уровень, награда {{ l.battle_reward }}, шанс победы {{ winChance(l) }}%
                                </option>
                            </select>
                        </div>
                        <button type="submit" class="btn btn-danger">Начать бой</button>
                    </form>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">Ваши танки</div>
                <div class="card-body">
                    <table class="table">
                        <tbody>
                            <tr v-for="tank in myTanks" :key="tank.id">
                                <td>{{ tank.name }} (уровень {{ tank.level_number }})</td>
                                <td v-if="activeBattle(tank) && secondsLeft(tank) > 0">
                                    Бой идёт, осталось {{ secondsLeft(tank) }} сек
                                    <button class="btn btn-warning btn-sm ms-2" @click="onCancel(tank)">Отменить</button>
                                </td>
                                <td v-else-if="activeBattle(tank)">
                                    <button class="btn btn-success btn-sm" @click="onClaim(tank)">Забрать награду</button>
                                </td>
                                <td v-else>Готов</td>
                            </tr>
                        </tbody>
                    </table>
                    <p v-if="myTanks.length === 0">У вас нет танков</p>
                </div>
            </div>
        </div>
    </div>
</template>
