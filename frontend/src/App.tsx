import { Route, Routes } from "react-router-dom";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<div>加载中…</div>} />
    </Routes>
  );
}
