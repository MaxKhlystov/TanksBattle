import { defineStore } from "pinia";
import { ref } from "vue";
import axios from "axios";
import { useUserStore } from '@/stores/user_store';   

export const useTanksStore = defineStore("tanksStore", () => {
    const userStore = useUserStore();   // добавлено

    const myTanks = ref([]);
    const levels = ref([]);
    const nations = ref([]);
    const battles = ref([]);
    const allCrewmen = ref([]);

    async function fetchTanks(params = {}) {
        try {
            const response = await axios.get('/api/tanks/', { params });
            myTanks.value = response.data;
            return response.data;
        } catch (error) {
            console.error('Ошибка загрузки танков:', error);
            myTanks.value = [];
            return [];
        }
    }

    async function fetchMyTanks() {
        const crewmanId = userStore.userInfo.crewman_id;
        if (!crewmanId) {
            myTanks.value = [];
            return [];
        }
        return await fetchTanks({ owner__id: crewmanId });
    }

    async function fetchTanksByUser(userId) {
        return await fetchTanks({ owner__id: userId });
    }

    async function createTank(data) {
        try {
            console.log("Sending create tank request...");
            console.log("CSRF header:", axios.defaults.headers.common['X-CSRFToken']);
            
            const response = await axios.post("/api/tanks/create/", data);
            await fetchMyTanks();
            await userStore.checkLogin();
            return response.data;
        } catch (error) {
            console.error("Ошибка создания танка:", error);
            console.error("Response headers:", error.response?.headers);
            console.error("Request headers:", error.config?.headers);
            throw error;
        }
    }

    async function upgradeTank(tankId) {
        try {
            const response = await axios.post(`/api/tanks/${tankId}/upgrade/`);
            await fetchMyTanks();
            await userStore.checkLogin();
            return response.data;
        } catch (error) {
            console.error("Ошибка улучшения танка:", error);
            throw error;
        }
    }

    async function sellTank(tankId) {
        try {
            const response = await axios.post(`/api/tanks/${tankId}/sell/`);
            await fetchMyTanks();
            await userStore.checkLogin();
            return response.data;
        } catch (error) {
            console.error("Ошибка продажи танка:", error);
            throw error;
        }
    }

    async function fetchLevels() {
        try {
            const response = await axios.get("/api/levels/");
            levels.value = response.data;
            return response.data;
        } catch (error) {
            console.error("Ошибка загрузки уровней:", error);
        }
    }

    async function createLevel(data) {
        try {
            console.log("Sending level data:", data);
            const response = await axios.post("/api/levels/", data);
            console.log("Response:", response.data);
            await fetchLevels();
            return response.data;
        } catch (error) {
            console.error("Ошибка создания уровня:", error);
            console.error("Response data:", error.response?.data);
            console.error("Status:", error.response?.status);
            throw error;
        }
    }

    async function deleteLevel(id) {
        try {
            await axios.delete(`/api/levels/${id}/`);
            await fetchLevels();
        } catch (error) {
            console.error("Ошибка удаления уровня:", error);
            throw error;
        }
    }

    async function fetchNations() {
        try {
            const response = await axios.get("/api/nations/");
            nations.value = response.data;
            return response.data;
        } catch (error) {
            console.error("Ошибка загрузки наций:", error);
        }
    }

    async function createNation(data) {
        try {
            const response = await axios.post("/api/nations/", data);
            await fetchNations();
            return response.data;
        } catch (error) {
            console.error("Ошибка создания нации:", error);
            throw error;
        }
    }

    async function updateNation(id, data) {
        try {
            const response = await axios.put(`/api/nations/${id}/`, data);
            await fetchNations();
            return response.data;
        } catch (error) {
            console.error("Ошибка обновления нации:", error);
            throw error;
        }
    }

    async function deleteNation(id) {
        try {
            await axios.delete(`/api/nations/${id}/`);
            await fetchNations();
        } catch (error) {
            console.error("Ошибка удаления нации:", error);
            throw error;
        }
    }

    async function fetchBattles() {
        try {
            const response = await axios.get("/api/battles/");
            battles.value = response.data;
            return response.data;
        } catch (error) {
            console.error("Ошибка загрузки боёв:", error);
        }
    }

    async function fetchBattlesByUser(userId) {
        try {
            const response = await axios.get(`/api/battles/?crewman=${userId}`);
            battles.value = response.data;
            return response.data;
        } catch (error) {
            console.error("Ошибка загрузки боёв пользователя:", error);
        }
    }

    async function startBattle(tankId, battleLevelId) {
        const response = await axios.post("/api/battles/start/", {
            tank_id: tankId,
            battle_level_id: battleLevelId
        });
        const battleId = response.data.id;
        const battleDuration = response.data.battle_duration || 5;
        
        return {
            battleId: battleId,
            battleDuration: battleDuration,
            ...response.data
        };
    }

    async function claimBattle(battleId) {
        const response = await axios.post(`/api/battles/${battleId}/claim/`);
        await fetchMyTanks();
        await fetchBattles();
        return response.data;
    }

    async function getBattleRemainingTime(battleId) {
        try {
            const response = await axios.get(`/api/battles/${battleId}/remaining-time/`);
            return response.data;
        } catch (error) {
            console.error('Ошибка получения времени боя:', error);
            return { remaining: 0, finished: true };
        }
    }

    async function fetchAllCrewmen() {
        try {
            const response = await axios.get('/api/crewman/list-users/');
            allCrewmen.value = response.data;
            return response.data;
        } catch (error) {
            console.error('Ошибка загрузки пользователей:', error);
        }
    }

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
        fetchMyTanks,
        fetchTanks,
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
        fetchAllCrewmen,
        getLevelInfo,
        getNationInfo,
        getBattleRemainingTime,
        fetchBattlesByUser,
        claimBattle,
        resetStore,
    };
});