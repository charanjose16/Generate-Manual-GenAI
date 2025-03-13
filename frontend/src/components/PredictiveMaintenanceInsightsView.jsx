import { useState, useEffect } from "react";
import {
  AlertCircle,
  Loader,
  Check,
  AlertTriangle,
  Activity,
  AlertOctagon,
  TrendingUp,
  PieChart as PieChartIcon,
  Wrench,
  Cpu,
  Calendar,
} from "lucide-react";
import { Pie } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
import PropTypes from "prop-types";
import {
  getFailureTrends,
  getRpmVsLoad,
  getTempVsVibration,
} from "../services/api";

// Register Chart.js components
ChartJS.register(ArcElement, Tooltip, Legend);

// Get the base URL from your .env file
const baseUrl = import.meta.env.VITE_BASE_URL;

/**
 * DynamicPieChart renders a dynamic, interactive pie chart using Chart.js.
 * It expects a statusData object where keys are categories and values are counts.
 */
const DynamicPieChart = ({ statusData }) => {
  const colorPalette = [
    "#FF6384",
    "#36A2EB",
    "#FFCE56",
    "#4BC0C0",
    "#9966FF",
    "#FF9F40",
    "#8BC34A",
    "#00BCD4",
    "#E91E63",
    "#9C27B0",
  ];
  const labels = Object.keys(statusData);
  let paletteIndex = 0;
  const backgroundColors = labels.map((label) => {
    if (label.toLowerCase() === "shutdown") {
      return "#e53e3e";
    } else {
      const color = colorPalette[paletteIndex % colorPalette.length];
      paletteIndex++;
      return color;
    }
  });
  const data = {
    labels,
    datasets: [
      {
        data: Object.values(statusData),
        backgroundColor: backgroundColors,
        hoverBackgroundColor: backgroundColors,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          usePointStyle: true,
          pointStyle: "circle",
          font: { size: 14 },
          color: "#2D3748",
        },
      },
      title: {
        display: true,
        text: "Motor Status Overview",
        font: { size: 18, weight: "bold" },
        color: "#2D3748",
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            const label = context.label || "";
            const value = context.raw;
            const total = context.chart.data.datasets[0].data.reduce(
              (acc, curr) => acc + curr,
              0
            );
            const percentage =
              total ? ((value / total) * 100).toFixed(2) + "%" : "0%";
            return label + ": " + percentage;
          },
        },
      },
    },
  };
  return <Pie data={data} options={options} />;
};

/**
 * Reusable component to render a bullet list.
 */
const BulletList = ({ items }) => (
  <ul className="list-none text-gray-800 text-sm space-y-1">
    {items.map((item, index) => (
      <li key={index} className="flex items-center">
        <div className="w-3 h-3 bg-teal-500 rounded-full inline-block mr-2" />
        <span>{item}</span>
      </li>
    ))}
  </ul>
);

/**
 * Parses a description string into bullet points if it contains multiple lines.
 */
const parseDescription = (desc) => {
  if (!desc) return null;
  const lines = desc
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
  return lines.length > 1 ? (
    <BulletList items={lines} />
  ) : (
    <p className="text-gray-800 text-sm">{desc}</p>
  );
};

/**
 * InsightCard displays a single insight.
 */
const InsightCard = ({ title, insight, getRiskIcon, parseDates }) => {
  const dates = parseDates(insight.dates);
  // Universal mapping for sub-heading icons
  const subHeadingIconMapping = {
    Description: (
      <Activity className="w-5 h-5 text-teal-500 inline-block mr-2" />
    ),
    Dates: (
      <Calendar className="w-5 h-5 text-teal-500 inline-block mr-2" />
    ),
    "AI Suggestions": (
      <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
    ),
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl">
      <h4 className="text-2xl font-bold text-gray-900 mb-4">
        <Activity className="w-6 h-6 text-teal-500 inline-block mr-2" />
        {title}
      </h4>
      <div className="flex items-center mb-8">
        <div className="mr-3">{getRiskIcon(insight.risk)}</div>
        <p className="text-gray-800 text-base">
          Risk Level: <span className="font-semibold">{insight.risk}</span>
        </p>
      </div>
      <div className="grid grid-cols-1 gap-6">
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
          <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
            {subHeadingIconMapping["Description"]}
            Description
          </h5>
          {parseDescription(insight.description)}
        </div>
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
          <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
            {subHeadingIconMapping["Dates"]}
            Dates
          </h5>
          {dates && dates.length > 0 ? (
            <BulletList items={dates} />
          ) : (
            <p className="text-gray-800 text-sm">No dates provided.</p>
          )}
        </div>
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
          <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
            {subHeadingIconMapping["AI Suggestions"]}
            AI Suggestions
          </h5>
          {parseDescription(insight.ai_suggestions)}
        </div>
      </div>
    </div>
  );
};

/**
 * PredictiveMaintenanceInsightsView fetches and displays maintenance insights.
 * Updated to accept a prop "months" instead of "duration".
 */
const PredictiveMaintenanceInsightsView = ({ motor, months }) => {
  const [insights, setInsights] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeView, setActiveView] = useState("anomaly_detection");

  // Parse dates JSON from API
  const parseDates = (datesStr) => {
    try {
      return JSON.parse(datesStr);
    } catch (e) {
      return [];
    }
  };

  // Return an icon based on risk level
  const getRiskIcon = (risk) => {
    switch (risk?.toLowerCase()) {
      case "low":
        return <Check className="w-6 h-6 text-green-500" />;
      case "moderate":
        return <AlertTriangle className="w-6 h-6 text-yellow-500" />;
      case "high":
        return <AlertCircle className="w-6 h-6 text-red-500" />;
      default:
        return null;
    }
  };

  // Define toggle views with updated icons for consistency
  const views = [
    {
      key: "anomaly_detection",
      label: "Anomaly Detection",
      icon: <Activity className="w-6 h-6 text-teal-500 mr-2" />,
    },
    {
      key: "high_failure_risk",
      label: "High Failure Risk",
      icon: <AlertOctagon className="w-6 h-6 text-teal-500 mr-2" />,
    },
    {
      key: "predictive_failure_modeling",
      label: "Predictive Failure Modeling",
      icon: <TrendingUp className="w-6 h-6 text-teal-500 mr-2" />,
    },
    {
      key: "pie_chart",
      label: "Pie Chart",
      icon: <PieChartIcon className="w-6 h-6 text-teal-500 mr-2" />,
    },
  ];

  useEffect(() => {
    if (motor && months) {
      const fetchInsights = async () => {
        setLoading(true);
        try {
          // Construct the query parameters
          const params = new URLSearchParams({
            motor_id: motor,
            months: months,
          });
          // Fetch data from the API using the baseUrl from .env
          const response = await fetch(
            `${baseUrl}/motor-maintenance?${params.toString()}`
          );
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const data = await response.json();
          setInsights(data.maintenance_insights);
          const pieData = data.motor_status_pie_data;
          const convertedStatusData = {};
          if (
            pieData &&
            pieData.labels &&
            pieData.datasets &&
            pieData.datasets[0]?.data
          ) {
            pieData.labels.forEach((label, index) => {
              convertedStatusData[label] = pieData.datasets[0].data[index];
            });
          } else {
            // Fallback data in case the API doesn't return pie chart data
            convertedStatusData["Operational"] = 70;
            convertedStatusData["Maintenance"] = 20;
            convertedStatusData["Failure"] = 10;
          }
          setStatusData(convertedStatusData);
        } catch (error) {
          setError("Error fetching predictive insights");
        } finally {
          setLoading(false);
        }
      };

      fetchInsights();
    }
  }, [motor, months]);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center mb-8 bg-blue-50 p-6 rounded-lg shadow-md">
        <Wrench className="w-10 h-10 text-teal-600 mr-3" />
        <h3 className="text-4xl font-bold text-gray-900">
          Predictive Maintenance Insights for {motor || "N/A"}{" "}
          {months && `- Last ${months} Month${months > 1 ? "s" : ""}`}
        </h3>
      </div>
      {/* If no motor or duration is selected, prompt the user */}
      {!(motor && months) ? (
        <p className="text-gray-800">
          Please select a motor and duration to view insights.
        </p>
      ) : loading ? (
        <div className="flex items-center space-x-2 text-teal-600">
          <Loader className="animate-spin h-6 w-6" />
          <span className="text-base">Loading insights...</span>
        </div>
      ) : error ? (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded-lg shadow-md">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        </div>
      ) : insights ? (
        <div>
          {/* Toggle Buttons */}
          <div className="flex flex-wrap gap-4 mb-8">
            {views.map((view) => (
              <button
                key={view.key}
                onClick={() => setActiveView(view.key)}
                className="flex items-center px-5 py-2 rounded-md shadow transition-colors font-medium bg-white text-black border border-black hover:bg-white hover:text-black"
              >
                {view.icon}
                {view.label}
              </button>
            ))}
          </div>
          {/* Selected View */}
          {activeView === "pie_chart" ? (
            <div className="flex flex-col items-center gap-4">
              <h4 className="text-2xl font-bold text-gray-900">
                Motor Status Overview
              </h4>
              <p className="text-gray-700 text-center max-w-md">
                This chart displays the distribution of the motor's status,
                including Operational, Maintenance, and Failure percentages.
              </p>
              {statusData ? (
                <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200 w-full max-w-md">
                  <DynamicPieChart statusData={statusData} />
                </div>
              ) : (
                <p className="text-gray-800">No pie chart data available.</p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-8">
              {activeView === "anomaly_detection" && (
                <InsightCard
                  title="Anomaly Detection"
                  insight={insights.anomaly_detection}
                  getRiskIcon={getRiskIcon}
                  parseDates={parseDates}
                />
              )}
              {activeView === "high_failure_risk" && (
                <InsightCard
                  title="High Failure Risk"
                  insight={insights.high_failure_risk}
                  getRiskIcon={getRiskIcon}
                  parseDates={parseDates}
                />
              )}
              {activeView === "predictive_failure_modeling" && (
                <InsightCard
                  title="Predictive Failure Modeling"
                  insight={insights.predictive_failure_modeling}
                  getRiskIcon={getRiskIcon}
                  parseDates={parseDates}
                />
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="text-gray-800">No analytics data available.</p>
      )}
    </div>
  );
};

PredictiveMaintenanceInsightsView.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

export default PredictiveMaintenanceInsightsView;