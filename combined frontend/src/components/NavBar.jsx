import { NavLink, useLocation } from "react-router-dom";
import logo from "../assets/ust-logo.png";
import { User } from "lucide-react";

const NavBar = () => {
  const location = useLocation();
  const title =
    location.pathname === "/user-manual-generator"
      ? "User Manual Generator"
      : "Analytics Dashboard";

  return (
    <nav className="w-full bg-teal-500 p-4 shadow-md flex items-center justify-between">
      {/* Left side: Logo and heading */}
      <div className="flex items-center gap-3">
        <img
          src={logo}
          alt="UST Logo"
          className="w-10 h-auto object-contain filter brightness-0 invert"
        />
        <h2 className="text-white text-xl font-semibold">{title}</h2>
      </div>
      {/* Right side: Toggle buttons and user info */}
      <div className="flex items-center gap-4">
        <NavLink
          to="/dashboard"
          // Inline styles ensure the link text remains white and without default underlines
          style={{ color: "white", textDecoration: "none" }}
          className={({ isActive }) =>
            isActive
              ? "bg-teal-600 text-white no-underline px-4 py-2 rounded transition-colors"
              : "bg-teal-500 text-white no-underline px-4 py-2 rounded hover:bg-teal-600 transition-colors"
          }
        >
          Dashboard
        </NavLink>
        <NavLink
          to="/user-manual-generator"
          style={{ color: "white", textDecoration: "none" }}
          className={({ isActive }) =>
            isActive
              ? "bg-teal-600 text-white no-underline px-4 py-2 rounded transition-colors"
              : "bg-teal-500 text-white no-underline px-4 py-2 rounded hover:bg-teal-600 transition-colors"
          }
        >
          User Manual Generator
        </NavLink>
        <div className="flex items-center gap-2">
          <User className="w-6 h-6 text-white" />
          <span className="text-white">Admin</span>
        </div>
      </div>
    </nav>
  );
};

export default NavBar;
