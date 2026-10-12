import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import EconomyPage from "./pages/EconomyPage";
import FinancePage from "./pages/FinancePage";
import MilitaryPage from "./pages/MilitaryPage";
import PoliticsPage from "./pages/PoliticsPage";
import SourcesPage from "./pages/SourcesPage";
import TasksPage from "./pages/TasksPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="politics" element={<PoliticsPage />} />
        <Route path="economy" element={<EconomyPage />} />
        <Route path="finance" element={<FinancePage />} />
        <Route path="military" element={<MilitaryPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
