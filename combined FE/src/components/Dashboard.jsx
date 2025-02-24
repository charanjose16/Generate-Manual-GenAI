import { Fragment, useState, useEffect } from "react";
import { Listbox, Transition } from "@headlessui/react";
import { BarChart, LineChart, Wrench, ChevronDown, Check } from "lucide-react";
import AnalyticsView from "./AnalyticsView";
import TrendAnalysisView from "./TrendAnalysisView";
import PredictiveMaintenanceInsightsView from "./PredictiveMaintenanceInsightsView";

const durations = [
  { value: "1", label: "Last 1 Month" },
  { value: "6", label: "Last 6 Months" },
  { value: "12", label: "Last 1 Year" },
  { value: "24", label: "Last 2 Years" },
  { value: "36", label: "Last 3 Years" },
  { value: "48", label: "Last 4 Years" },
  { value: "60", label: "Last 5 Years" },
];
const baseUrl = import.meta.env.VITE_BASE_URL;

const Dashboard = () => {
  const [motors, setMotors] = useState([]);
  const [selectedMotor, setSelectedMotor] = useState("");
  const [selectedDuration, setSelectedDuration] = useState("");
  const [activeView, setActiveView] = useState("");

  // Fetch motor IDs from the API
  useEffect(() => {
    const fetchMotors = async () => {
      try {
        const response = await fetch(`${baseUrl}/motors`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log("Response from API:", data);
        setMotors(data.motors || []);
      } catch (error) {
        console.error("Error fetching motors:", error);
      }
    };
    fetchMotors();
  }, []);

  const months = selectedDuration ? parseInt(selectedDuration, 10) : null;

  const renderView = () => {
    if (!selectedMotor || !months) {
      return (
        <div className="w-full min-w-full">
          <p className="text-gray-500 text-center mt-6">
            Please select a motor and duration.
          </p>
        </div>
      );
    }
    console.log("Rendering view for", activeView, {
      motor: selectedMotor,
      months,
    });
    switch (activeView) {
      case "analytics":
        return <AnalyticsView motor={selectedMotor} months={months} />;
      case "trend":
        return <TrendAnalysisView motor={selectedMotor} months={months} />;
      case "predictive":
        return (
          <PredictiveMaintenanceInsightsView
            motor={selectedMotor}
            months={months}
          />
        );
      default:
        return (
          <div className="w-full min-w-full">
            <p className="text-gray-500 text-center mt-6">
              Select an option to view insights.
            </p>
          </div>
        );
    }
  };

  return (
    // Outer container fills full width and full height
    <div className="w-full min-h-screen bg-gray-200 text-gray-800 flex flex-col overflow-x-hidden">
      <div className="flex-1 p-6 w-full">
        <div className="w-full flex flex-col">
          {/* Dropdowns */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 mb-6 w-full">
            {/* Motor Dropdown */}
            <div className="w-full md:w-1/2">
              <Listbox value={selectedMotor} onChange={setSelectedMotor}>
                {({ open }) => (
                  <div className="relative w-full">
                    <Listbox.Button className="w-full bg-gray-200 text-black p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-teal-500 text-left">
                      <span>{selectedMotor || "Select a Motor"}</span>
                      <ChevronDown
                        className={`absolute right-3 top-2.5 text-black transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </Listbox.Button>
                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                    >
                      <Listbox.Options className="absolute z-10 mt-1 w-full bg-gray-200 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-gray-300 overflow-auto focus:outline-none">
                        {motors.map((motor, idx) => (
                          <Listbox.Option
                            key={idx}
                            value={motor}
                            className={({ active }) =>
                              `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
                                active ? "bg-teal-300 text-black" : "text-black"
                              }`
                            }
                          >
                            {({ selected }) => (
                              <>
                                <span
                                  className={`block truncate ${
                                    selected ? "font-medium" : "font-normal"
                                  }`}
                                >
                                  {motor}
                                </span>
                                {selected && (
                                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-black">
                                    <Check className="w-5 h-5" />
                                  </span>
                                )}
                              </>
                            )}
                          </Listbox.Option>
                        ))}
                      </Listbox.Options>
                    </Transition>
                  </div>
                )}
              </Listbox>
            </div>
            {/* Duration Dropdown */}
            <div className="w-full md:w-1/2">
              <Listbox value={selectedDuration} onChange={setSelectedDuration}>
                {({ open }) => (
                  <div className="relative w-full">
                    <Listbox.Button className="w-full bg-gray-200 text-black p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-teal-500 text-left">
                      <span>
                        {durations.find((d) => d.value === selectedDuration)
                          ?.label || "Select a Duration"}
                      </span>
                      <ChevronDown
                        className={`absolute right-3 top-2.5 text-black transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </Listbox.Button>
                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                    >
                      <Listbox.Options className="absolute z-10 mt-1 w-full bg-gray-200 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-gray-300 overflow-auto focus:outline-none">
                        {durations.map((duration, idx) => (
                          <Listbox.Option
                            key={idx}
                            value={duration.value}
                            className={({ active }) =>
                              `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
                                active ? "bg-teal-300 text-black" : "text-black"
                              }`
                            }
                          >
                            {({ selected }) => (
                              <>
                                <span
                                  className={`block truncate ${
                                    selected ? "font-medium" : "font-normal"
                                  }`}
                                >
                                  {duration.label}
                                </span>
                                {selected && (
                                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-black">
                                    <Check className="w-5 h-5" />
                                  </span>
                                )}
                              </>
                            )}
                          </Listbox.Option>
                        ))}
                      </Listbox.Options>
                    </Transition>
                  </div>
                )}
              </Listbox>
            </div>
          </div>
          {/* Action Buttons */}
          <div className="flex flex-wrap justify-center gap-4 mb-6 w-full">
            <button
              onClick={() => setActiveView("analytics")}
              className={`flex items-center gap-2 px-4 py-2 rounded-md shadow-md transition-colors duration-200 text-black ${
                activeView === "analytics"
                  ? "bg-teal-200"
                  : "bg-teal-100 hover:bg-teal-200"
              }`}
            >
              <BarChart className="w-5 h-5 text-teal-500" /> Generate Analytics
            </button>
            <button
              onClick={() => setActiveView("trend")}
              className={`flex items-center gap-2 px-4 py-2 rounded-md shadow-md transition-colors duration-200 text-black ${
                activeView === "trend"
                  ? "bg-teal-200"
                  : "bg-teal-100 hover:bg-teal-200"
              }`}
            >
              <LineChart className="w-5 h-5 text-teal-500" /> Generate Trend
              Analysis
            </button>
            <button
              onClick={() => setActiveView("predictive")}
              className={`flex items-center gap-2 px-4 py-2 rounded-md shadow-md transition-colors duration-200 text-black ${
                activeView === "predictive"
                  ? "bg-teal-200"
                  : "bg-teal-100 hover:bg-teal-200"
              }`}
            >
              <Wrench className="w-5 h-5 text-teal-500" /> Predictive
              Maintenance Insights
            </button>
          </div>
          {/* Render the Selected View */}
          <div className="bg-white p-6 rounded-md shadow-md w-full min-w-full">
            {renderView()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
