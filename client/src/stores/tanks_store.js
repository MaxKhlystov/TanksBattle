import { defineStore } from "pinia";
import { ref } from "vue";
import axios from "axios";

export const useTanksStore = defineStore("tanksStore", () => {
    const myTanks = ref([]);
    const levels = ref([]);
    const nations = ref([]);
    const battles = ref([]);
    const allCrewmen = ref([]);

    async function fetchTanks(params = {}) {
        const r = await axios.get("/api/tanks/", { params });
        myTanks.value = r.data;
    }

    async function createTank(data) {
        await axios.post("/api/tanks/create/", data);
    }

    async function upgradeTank(id) {
        await axios.post(`/api/tanks/${id}/upgrade/`);
    }

    async function updateTank(id, data) {
       await axios.put(`/api/tanks/${id}/`, data);
    }

    async function sellTank(id) {
        await axios.post(`/api/tanks/${id}/sell/`);
    }

    async function fetchLevels() {
        const r = await axios.get("/api/levels/");
        levels.value = r.data;
    }

    async function createLevel(data) {
        await axios.post("/api/levels/", data);
        await fetchLevels();
    }

    async function deleteLevel(id) {
        await axios.delete(`/api/levels/${id}/`);
        await fetchLevels();
    }

    async function fetchNations() {
        const r = await axios.get("/api/nations/");
        nations.value = r.data;
    }

    async function createNation(data) {
        await axios.post("/api/nations/", data);
        await fetchNations();
    }

    async function updateNation(id, data) {
        await axios.put(`/api/nations/${id}/`, data);
        await fetchNations();
    }

    async function deleteNation(id) {
        await axios.delete(`/api/nations/${id}/`);
        await fetchNations();
    }

    async function fetchBattles(params = {}) {
        const r = await axios.get("/api/battles/", { params });
        battles.value = r.data;
    }

    async function startBattle(tankId, battleLevelId) {
        await axios.post("/api/battles/start/", { tank_id: tankId, battle_level_id: battleLevelId });
    }

    async function cancelBattle(id) {
        await axios.post(`/api/battles/${id}/cancel/`);
    }

    async function claimBattle(id) {
        const r = await axios.post(`/api/battles/${id}/claim/`);
        return r.data;
    }

    async function fetchAllCrewmen() {
        const r = await axios.get("/api/crewman/list-users/");
        allCrewmen.value = r.data;
    }

    async function updateCrewman(crewman) {
        await axios.put(`/api/crewman/${crewman.id}/`, {
            credits: crewman.credits,
            garage_slots: crewman.garage_slots
        });
    }

    function getLevelInfo(id) {
        return levels.value.find(l => l.id === id);
    }

    function resetStore() {
        myTanks.value = [];
        battles.value = [];
        allCrewmen.value = [];
    }

    return {
        myTanks, levels, nations, battles, allCrewmen,
        fetchTanks, createTank, upgradeTank, sellTank,
        fetchLevels, createLevel, deleteLevel,
        fetchNations, createNation, updateNation, deleteNation,
        fetchBattles, startBattle, cancelBattle, claimBattle,
        fetchAllCrewmen, updateCrewman,
        getLevelInfo, resetStore
    };
});
