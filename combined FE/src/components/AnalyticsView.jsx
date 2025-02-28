import { useState, useEffect } from "react";
import PropTypes from "prop-types";
import { Tab } from "@headlessui/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Loader,
  CheckCircle,
  AlertCircle,
  Info,
  Zap,
  Activity,
  Cpu,
  TrendingUp,
  Smartphone,
  PieChart,
  List,
  ClipboardList,
} from "lucide-react";

const parseAiObservation = (text) => {
  // Expected format:
  // "Observation: <observation text> Insight: <insight text> Recommendation: <recommendation text>"
  const regex =
    /Observation:\s*(.*?)\s*Insight:\s*(.*?)\s*Recommendation:\s*(.*)/i;
  const match = text.match(regex);
  if (match) {
    return {
      observation: match[1],
      insight: match[2],
      recommendation: match[3],
    };
  }
  // Fallback: return the whole text as observation.
  return { observation: text, insight: "", recommendation: "" };
};

const AnalyticsView = ({ motor, months }) => {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [aiObservations, setAiObservations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const baseUrl = import.meta.env.VITE_BASE_URL;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    // Timeout in case the API takes too long (10 sec).
    const errorTimeout = setTimeout(() => {
      setError("Analytics data is not available at the moment.");
      setLoading(false);
      controller.abort();
    }, 10000);

    const fetchAnalytics = async () => {
      // Always start by showing the loading spinner.
      setLoading(true);
      setError(null);
      const startTime = Date.now();

      try {
        const url = `${baseUrl}/api/analytics?motor_id=${motor}&months=${months}`;
        const response = await fetch(url, { signal });

        // If a 404 is returned, treat it as "no data found".
        if (!response.ok) {
          if (response.status === 404) {
            console.warn("API returned 404 - No data found.");
            setAnalyticsData({});
            return;
          }
          throw new Error("Network response was not ok");
        }

        const data = await response.json();
        console.log("Analytics API response:", data);
        if (data && data.analytics) {
          setAnalyticsData(data.analytics);
          setAiObservations(data.ai_observations);
        } else {
          console.warn("API did not return analytics data as expected.");
          setAnalyticsData({});
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setError("Error fetching analytics data.");
          console.error("Error fetching analytics:", err);
        }
      } finally {
        clearTimeout(errorTimeout);
        // Calculate elapsed time.
        const elapsed = Date.now() - startTime;
        // Ensure the loading state remains for at least 0.3 seconds.
        if (elapsed < 300) {
          setTimeout(() => {
            setLoading(false);
          }, 300 - elapsed);
        } else {
          setLoading(false);
        }
      }
    };

    if (motor && months !== undefined) {
      fetchAnalytics();
    }

    return () => {
      clearTimeout(errorTimeout);
      controller.abort();
    };
  }, [motor, months, baseUrl]);

  // Display the loader while loading.
  if (loading) {
    return (
      <div className="flex items-center space-x-2 text-teal-600 p-6">
        <Loader className="animate-spin h-6 w-6" />
        <span className="text-base">Loading analytics...</span>
      </div>
    );
  }

  if (error) return <p className="text-red-600 p-6">{error}</p>;

  // After loading, if analyticsData is empty, display a "no data" message.
  if (!analyticsData || Object.keys(analyticsData).length === 0)
    return <p className="p-6">No analytics data available.</p>;

  // Prepare chart data for Recharts.
  const chartData = [
    {
      name: "Voltage",
      avg: analyticsData.voltage?.avg,
      max: analyticsData.voltage?.max,
      min: analyticsData.voltage?.min,
    },
    {
      name: "Current",
      avg: analyticsData.current?.avg,
      max: analyticsData.current?.max,
      min: analyticsData.current?.min,
    },
    {
      name: "Power",
      avg: analyticsData.power?.avg,
      max: analyticsData.power?.max,
      min: analyticsData.power?.min,
    },
    {
      name: "Load",
      avg: analyticsData.load?.avg,
      max: analyticsData.load?.max,
      min: analyticsData.load?.min,
    },
    {
      name: "Vibration",
      avg: analyticsData.vibration?.avg,
      max: analyticsData.vibration?.max,
      min: analyticsData.vibration?.min,
    },
  ];

  const metricIcons = {
    Voltage: <Zap className="w-8 h-8 text-teal-600" />,
    Current: <Activity className="w-8 h-8 text-teal-600" />,
    Power: <Cpu className="w-8 h-8 text-teal-600" />,
    Load: <TrendingUp className="w-8 h-8 text-teal-600" />,
    Vibration: <Smartphone className="w-8 h-8 text-teal-600" />,
  };

  const tabs = [
    {
      key: "chart",
      label: "Bar Chart",
      icon: <PieChart className="w-5 h-5 mr-1 text-teal-500" />,
    },
    {
      key: "metrics",
      label: "Metrics",
      icon: <List className="w-5 h-5 mr-1 text-teal-500" />,
    },
    {
      key: "details",
      label: "Additional Details",
      icon: <ClipboardList className="w-5 h-5 mr-1 text-teal-500" />,
    },
    {
      key: "ai",
      label: "AI Observations",
      icon: <Info className="w-5 h-5 mr-1 text-teal-500" />,
    },
  ];

  return (
    <div className="p-6">
      <div className="flex items-center mb-8 bg-blue-50 p-6 rounded-lg shadow-md">
        <PieChart className="w-10 h-10 text-teal-600 mr-4" />
        <h2 className="text-4xl font-bold text-gray-900">
          Analytics for Motor {motor} over the past {months}{" "}
          {months > 1 ? "months" : "month"}
        </h2>
      </div>

      <Tab.Group>
        <Tab.List className="flex space-x-4 mb-6">
          {tabs.map((tab) => (
            <Tab
              key={tab.key}
              className={({ selected }) =>
                "px-4 py-2 rounded-md border border-black bg-gray-200 text-black font-medium focus:outline-none"
              }
            >
              <div className="flex items-center">
                {tab.icon}
                {tab.label}
              </div>
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels>
          <Tab.Panel className="p-4 border border-gray-300 rounded-md">
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={chartData}
                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="avg" fill="#8884d8" name="Average" />
                <Bar dataKey="max" fill="#82ca9d" name="Maximum" />
                <Bar dataKey="min" fill="#ffc658" name="Minimum" />
              </BarChart>
            </ResponsiveContainer>
          </Tab.Panel>
          <Tab.Panel className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-4">
            {chartData.map((metric) => (
              <div
                key={metric.name}
                className="bg-white border border-teal-300 rounded-lg shadow-md p-6"
              >
                <div className="flex items-center mb-4">
                  {metricIcons[metric.name]}
                  <h4 className="text-2xl font-bold text-teal-700 ml-3">
                    {metric.name}
                  </h4>
                </div>
                <div className="text-gray-700">
                  <div className="flex justify-between mb-2">
                    <span className="font-semibold">Average:</span>
                    <span>{metric.avg}</span>
                  </div>
                  <div className="flex justify-between mb-2">
                    <span className="font-semibold">Maximum:</span>
                    <span>{metric.max}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-semibold">Minimum:</span>
                    <span>{metric.min}</span>
                  </div>
                </div>
              </div>
            ))}
          </Tab.Panel>
          <Tab.Panel className="p-4 border border-teal-300 rounded-lg">
            <h4 className="text-lg font-semibold mb-2 text-teal-700">
              Additional Analytics Details
            </h4>
            <div className="flex justify-between text-gray-700 mb-1">
              <span className="font-semibold">Failures:</span>
              <span>{analyticsData.failures}</span>
            </div>
            <div className="flex justify-between text-gray-700">
              <span className="font-semibold">Period:</span>
              <span>
                {analyticsData.period?.start} to {analyticsData.period?.end}
              </span>
            </div>
          </Tab.Panel>
          <Tab.Panel className="p-4 border border-teal-300 rounded-lg">
            <h4 className="text-lg font-semibold mb-4 flex items-center text-teal-700">
              <Cpu size={24} className="text-teal-500 mr-2" />
              AI Observations:
            </h4>
            <div className="space-y-4">
              {aiObservations
                .split(/\n\s*\n/)
                .filter((block) => block.trim() !== "")
                .map((obsText, index) => {
                  const { observation, insight, recommendation } =
                    parseAiObservation(obsText);
                  return (
                    <div
                      key={index}
                      className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left"
                    >
                      <div className="flex items-center mb-4">
                        <Cpu size={24} className="text-teal-500 mr-2" />
                        <h4 className="text-2xl font-bold text-gray-900">
                          AI Observation
                        </h4>
                      </div>
                      <ul className="list-none pl-0 text-gray-800 text-sm text-left">
                        <li className="flex items-start mb-2">
                          <div className="w-3 h-3 bg-teal-500 rounded-full inline-block mr-2 mt-1 flex-shrink-0"></div>
                          <span>
                            <span className="font-semibold">Observation:</span>{" "}
                            {observation}
                          </span>
                        </li>
                        {insight && insight.trim() !== "" && (
                          <li className="flex items-start mb-2">
                            <div className="w-3 h-3 bg-teal-500 rounded-full inline-block mr-2 mt-1 flex-shrink-0"></div>
                            <span>
                              <span className="font-semibold">Insight:</span>{" "}
                              {insight}
                            </span>
                          </li>
                        )}
                        {recommendation && recommendation.trim() !== "" && (
                          <li className="flex items-start">
                            <div className="w-3 h-3 bg-teal-500 rounded-full inline-block mr-2 mt-1 flex-shrink-0"></div>
                            <span>
                              <span className="font-semibold">
                                Recommendation:
                              </span>{" "}
                              {recommendation}
                            </span>
                          </li>
                        )}
                      </ul>
                    </div>
                  );
                })}
            </div>
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
};

AnalyticsView.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

export default AnalyticsView;