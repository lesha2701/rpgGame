import { Navigate, Route, Routes } from "react-router-dom";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { AppShell } from "@/components/layout/AppShell";
import { AdminAppIconsPage } from "@/pages/admin/AdminAppIconsPage";
import { AdminCatalogPage } from "@/pages/admin/AdminCatalogPage";
import { AdminChestFormPage } from "@/pages/admin/AdminChestFormPage";
import { AdminChestsPage } from "@/pages/admin/AdminChestsPage";
import { AdminDashboardPage } from "@/pages/admin/AdminDashboardPage";
import { AdminResourceFormPage } from "@/pages/admin/AdminResourceFormPage";
import { AdminResourceListPage } from "@/pages/admin/AdminResourceListPage";
import { AdminUserDetailPage } from "@/pages/admin/AdminUserDetailPage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { AlchemyPage } from "@/pages/AlchemyPage";
import { ArenaMatchPage } from "@/pages/ArenaMatchPage";
import { ArenaPage } from "@/pages/ArenaPage";
import { BattleHubPage } from "@/pages/BattleHubPage";
import { BestiaryPage } from "@/pages/BestiaryPage";
import { CampaignBattlePage } from "@/pages/CampaignBattlePage";
import { CampaignNodePage } from "@/pages/CampaignNodePage";
import { CampaignPage } from "@/pages/CampaignPage";
import { CharacterDetailPage } from "@/pages/CharacterDetailPage";
import { ChestOpeningPage } from "@/pages/ChestOpeningPage";
import { ChestsPage } from "@/pages/ChestsPage";
import { CollectionPage } from "@/pages/CollectionPage";
import { EnemyDetailPage } from "@/pages/EnemyDetailPage";
import { EquipmentPage } from "@/pages/EquipmentPage";
import { ExpeditionsPage } from "@/pages/ExpeditionsPage";
import { FindPairsPage } from "@/pages/FindPairsPage";
import { HeroPage } from "@/pages/HeroPage";
import { HeroProgressionPage } from "@/pages/HeroProgressionPage";
import { InventoryPage } from "@/pages/InventoryPage";
import { LeaderboardsPage } from "@/pages/LeaderboardsPage";
import { MemorySequencePage } from "@/pages/MemorySequencePage";
import { MorePage } from "@/pages/MorePage";
import { ProfilePage } from "@/pages/ProfilePage";
import { QuestsPage } from "@/pages/QuestsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TavernDicePage } from "@/pages/TavernDicePage";
import { ThreeCupsPage } from "@/pages/ThreeCupsPage";
import { TrainingDummyPage } from "@/pages/TrainingDummyPage";

export function App() {
  return (
    <Routes>
      <Route
        path="/admin"
        element={
          <AdminGuard>
            <AdminLayout />
          </AdminGuard>
        }
      >
        <Route index element={<AdminDashboardPage />} />
        <Route path="app-icons" element={<AdminAppIconsPage />} />
        <Route path="chests" element={<AdminChestsPage />} />
        <Route path="chests/new" element={<AdminChestFormPage />} />
        <Route path="chests/:chestId/edit" element={<AdminChestFormPage />} />
        <Route path="catalog" element={<AdminCatalogPage />} />
        <Route path="catalog/:resource" element={<AdminResourceListPage />} />
        <Route path="catalog/:resource/new" element={<AdminResourceFormPage />} />
        <Route path="catalog/:resource/:id/edit" element={<AdminResourceFormPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:userId" element={<AdminUserDetailPage />} />
      </Route>

      <Route element={<AppShell />}>
        {/* "/" and "/hero" used to be separate screens (Home + Hero) —
            merged into one; "/" just points at the same place so the
            BottomNav's "Герой" tab (which links to "/hero") is the one
            that ever shows active, deep links included. */}
        <Route path="/" element={<Navigate to="/hero" replace />} />
        <Route path="/hero" element={<HeroPage />} />
        <Route path="/hero/progression" element={<HeroProgressionPage />} />
        <Route path="/collection" element={<CollectionPage />} />
        <Route path="/collection/:templateId" element={<CharacterDetailPage />} />
        <Route path="/bestiary" element={<BestiaryPage />} />
        <Route path="/bestiary/:enemyId" element={<EnemyDetailPage />} />
        <Route path="/battle" element={<BattleHubPage />} />
        <Route path="/campaign" element={<CampaignPage />} />
        <Route path="/campaign/nodes/:nodeId" element={<CampaignNodePage />} />
        <Route path="/campaign/battles/:battleId" element={<CampaignBattlePage />} />
        <Route path="/battle/memory" element={<MemorySequencePage />} />
        <Route path="/battle/pairs" element={<FindPairsPage />} />
        <Route path="/battle/dummy" element={<TrainingDummyPage />} />
        <Route path="/battle/alchemy" element={<AlchemyPage />} />
        <Route path="/battle/dice" element={<TavernDicePage />} />
        <Route path="/battle/cups" element={<ThreeCupsPage />} />
        <Route path="/arena" element={<ArenaPage />} />
        <Route path="/arena/matches/:matchId" element={<ArenaMatchPage />} />
        <Route path="/leaderboards" element={<LeaderboardsPage />} />
        <Route path="/chests" element={<ChestsPage />} />
        <Route path="/chests/:chestId/open" element={<ChestOpeningPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/equipment" element={<EquipmentPage />} />
        <Route path="/quests" element={<QuestsPage />} />
        <Route path="/expeditions" element={<ExpeditionsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
