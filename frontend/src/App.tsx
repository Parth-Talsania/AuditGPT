import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/analyze/:ticker" element={<Dashboard />} />
        <Route path="/analyze" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
