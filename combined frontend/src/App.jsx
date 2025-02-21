import Dashboard from "./components/Dashboard";
import UserManualGenerator from "./components/UserManualGenerator";
import Footer from "./components/Footer";
import NavBar from "./components/NavBar";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <div className="w-screen min-h-screen flex flex-col">
        <NavBar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/user-manual-generator" element={<UserManualGenerator/>} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
}

export default App;
