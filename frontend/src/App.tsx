import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import BacktestPage from "./pages/BacktestPage";
import ScenariosPage from "./pages/ScenariosPage";
import DataTablePage from "./pages/DataTablePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/scenarios" element={<ScenariosPage />} />
          <Route path="/data" element={<DataTablePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
