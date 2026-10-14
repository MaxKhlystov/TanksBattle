import { defineStore } from "pinia";
import { ref } from "vue";
import axios from "axios";
import { useUserStore } from '@/stores/user_store';

// Ошибки запросов, меняющих данные, не перехватываются здесь:
// их показывает вызывающая страница (через showError + getErrorMessage).
export const useTanksStore = defineStore("tanksStore", () => {
    const userStore = useUserStore();
    const myTanks = ref([]);
    const levels = ref([]);
    const nations = ref([]);
    const battles = ref([]);
    const allCrewmen = ref([]);

    // Загрузка списка с сервера; при ошибке список очищается
    async function load(url, target, params = {}) {
        try {
            const response = await axios.get(url, { params });
            target.value = response.data;
        } catch (error) {
            console.error(`Ошибка загрузки ${url}:`, error);
            target.value = [];
        }
        return target.value;
    }

    // --- Танки ---
    function fetchTanks(params = {}) {
        return load('/api/tanks/', myTanks, params);
    }

    async function fetchMyTanks() {
        const crewmanId = userStore.userInfo.crewman_id;
        if (!crewmanId) {
            myTanks.value = [];
            return [];
        }
        return fetchTanks({ owner__id: crewmanId });
    }

    function fetchTanksByUser(userId) {
        return fetchTanks({ owner__id: userId });
    }

    async function createTank(data) {
        const response = await axios.post("/api/tanks/create/", data);
        await fetchMyTanks();
        await userStore.checkLogin();
        return response.data;
    }

    // После улучшения/продажи список перезагружает страница (она знает, чей ангар открыт)
    async function upgradeTank(tankId) {
        const response = await axios.post(`/api/tanks/${tankId}/upgrade/`);
        return response.data;
    }

    async function sellTank(tankId) {
        const response = await axios.post(`/api/tanks/${tankId}/sell/`);
        return response.data;
    }

    // --- Уровни ---
    function fetchLevels() {
        return load("/api/levels/", levels);
    }

    async function createLevel(data) {
        const response = await axios.post("/api/levels/", data);
        await fetchLevels();
        return response.data;
    }

    async function deleteLevel(id) {
        await axios.delete(`/api/levels/${id}/`);
        await fetchLevels();
    }

    // --- Нации ---
    function fetchNations() {
        return load("/api/nations/", nations);
    }

    async function createNation(data) {
        const response = await axios.post("/api/nations/", data);
        await fetchNations();
        return response.data;
    }

    async function updateNation(id, data) {
        const response = await axios.put(`/api/nations/${id}/`, data);
        await fetchNations();
        return response.data;
    }

    async function deleteNation(id) {
        await axios.delete(`/api/nations/${id}/`);
        await fetchNations();
    }

    // --- Бои ---
    function fetchBattles(params = {}) {
        return load("/api/battles/", battles, params);
    }

    // Ответ сервера: запись боя (id, tank, battle_level, ...) + battle_duration в секундах
    async function startBattle(tankId, battleLevelId) {
        const response = await axios.post("/api/battles/start/", {
            tank_id: tankId,
            battle_level_id: battleLevelId
        });
        return response.data;
    }

    async function cancelBattle(battleId) {
        await axios.post(`/api/battles/${battleId}/cancel/`);
        await fetchMyTanks();
        await fetchBattles();
    }

    async function claimBattle(battleId) {
        const response = await axios.post(`/api/battles/${battleId}/claim/`);
        await fetchMyTanks();
        await fetchBattles();
        await userStore.checkLogin();
        return response.data;
    }

    async function getBattleRemainingTime(battleId) {
        try {
            const response = await axios.get(`/api/battles/${battleId}/remaining-time/`);
            return response.data;
        } catch (error) {
            console.error('Ошибка получения времени боя:', error);
            return { remaining: 0, finished: false, error: true };
        }
    }

    // --- Игроки (для администратора) ---
    function fetchAllCrewmen() {
        return load('/api/crewman/list-users/', allCrewmen);
    }

    async function updateCrewman(crewman) {
        const response = await axios.put(`/api/crewman/${crewman.id}/`, {
            credits: crewman.credits,
            garage_slots: crewman.garage_slots
        });
        return response.data;
    }

    // --- Справочники ---
    function getLevelInfo(levelId) {
        return levels.value.find(l => l.id === levelId);
    }

    function getNationInfo(nationId) {
        return nations.value.find(n => n.id === nationId);
    }

    function resetStore() {
        myTanks.value = [];
        levels.value = [];
        nations.value = [];
        battles.value = [];
        allCrewmen.value = [];
    }

    return {
        myTanks,
        levels,
        nations,
        battles,
        allCrewmen,
        fetchTanks,
        fetchMyTanks,
        fetchTanksByUser,
        createTank,
        upgradeTank,
        sellTank,
        fetchLevels,
        createLevel,
        deleteLevel,
        fetchNations,
        createNation,
        updateNation,
        deleteNation,
        fetchBattles,
        startBattle,
        cancelBattle,
        claimBattle,
        getBattleRemainingTime,
        fetchAllCrewmen,
        updateCrewman,
        getLevelInfo,
        getNationInfo,
        resetStore,
    };
});
