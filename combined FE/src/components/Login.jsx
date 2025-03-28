import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Transition } from "@headlessui/react";
import { Eye, EyeOff } from "lucide-react";
import ustLogo from "../assets/ust-logo.png";

const Login = () => {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [notification, setNotification] = useState({ open: false, type: "", message: "" });
  const navigate = useNavigate();

  const handleLogin = () => {
    if (userId === "admin@ust" && password === "adminust") {
      sessionStorage.setItem("isAuthenticated", "true");
      navigate("/dashboard");
    } else {
      showNotification("error", "Invalid credentials. Please try again.");
    }
  };

  const handleForgotPassword = () => {
    showNotification("info", "For password recovery, please contact your administrator.");
  };

  const showNotification = (type, message) => {
    setNotification({ open: true, type, message });
    setTimeout(() => {
      setNotification({ open: false, type: "", message: "" });
    }, 3000);
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-800 to-teal-500 text-white">
      {/* Top header with UST Logo in left corner */}
      <header className="absolute top-6 left-6">
        <img 
          src={ustLogo} 
          alt="UST Logo" 
          className="h-22 w-auto filter brightness-0 invert" 
        />
      </header>

      {/* Login form container */}
      <main className="flex-grow flex items-center justify-center px-4">
        <div className="bg-white text-gray-900 rounded-xl shadow-2xl p-8 w-full max-w-md border border-gray-100/20 transform transition-all duration-300 hover:scale-[1.02]">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-teal-700 mb-2">Regal Product Services Portal</h2>
            <p className="text-gray-500 text-sm">Enter Credentials to access your Account</p>
          </div>
          
          {/* User ID Input */}
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-medium mb-2">User ID</label>
            <input
              type="text"
              placeholder="Enter your username"
              className="w-full bg-gray-50 border border-gray-300 rounded-md px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 transition duration-300"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
          
          {/* Password Input */}
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-medium mb-2">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                className="w-full bg-gray-50 border border-gray-300 rounded-md px-4 py-3 pr-10 focus:outline-none focus:ring-2 focus:ring-teal-500 transition duration-300"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-teal-600"
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {/* Forgot Password */}
          <div className="flex justify-end mb-4">
            <p 
              onClick={handleForgotPassword} 
              className="text-teal-600 hover:text-teal-800 text-sm cursor-pointer transition duration-300"
            >
              Forgot Password?
            </p>
          </div>

          {/* Login Button */}
          <button
            onClick={handleLogin}
            className="w-full bg-white border border-teal-600 text-teal-600 hover:bg-teal-50 hover:border-teal-700 hover:text-teal-700 font-semibold py-3 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:scale-[1.02] active:scale-[0.98]"
          >
            Login
          </button>
        </div>
      </main>

      {/* Notification Popup */}
      <Transition
        show={notification.open}
        enter="transition-opacity duration-300"
        enterFrom="opacity-0"
        enterTo="opacity-100"
        leave="transition-opacity duration-300"
        leaveFrom="opacity-100"
        leaveTo="opacity-0"
      >
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
          <div className={`px-4 py-2 rounded-lg shadow-lg text-white ${
            notification.type === "error" ? "bg-red-600" : "bg-teal-600"
          }`}>
            {notification.message}
          </div>
        </div>
      </Transition>
    </div>
  );
};

export default Login;