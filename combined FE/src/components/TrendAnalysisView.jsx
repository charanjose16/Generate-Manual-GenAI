/* eslint-disable react/prop-types */
import  { useState, useEffect } from "react";
import { Tab, Transition } from "@headlessui/react";
import {
  ChartBar,
  AlertCircle,
  TrendingUp,
  Sun,
  Loader,
  Cpu,
} from "lucide-react";
import PropTypes from "prop-types";
import {
  BarChart,
  Bar,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend as RechartLegend,
  Line,
  ScatterChart,
  Scatter,
  Dot,
  ResponsiveContainer,
} from "recharts";
import {
  getFailureTrends,
  getRpmVsLoad,
  getTempVsVibration,
} from "../services/api";
// TrendAnalysisView.jsx

// Import and register Chart.js components
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend } from "chart.js";
// Manually assign ids to Tooltip and Legend if missing (fixes the "class does not have id" error)
if (!ChartTooltip.id) ChartTooltip.id = "tooltip";
if (!Legend.id) Legend.id = "legend";

ChartJS.register(ArcElement, ChartTooltip, Legend);


// LoadingSpinner component using Loader icon and teal color.
const LoadingSpinner = () => (
  <div className="flex items-center space-x-2 text-teal-600 justify-center py-10">
    <Loader className="animate-spin h-6 w-6" />
    <span className="text-base">Loading data...</span>
  </div>
);

const CustomDot = ({ cx, cy, stroke }) => {
  const [isHovered, setIsHovered] = useState(false);
  return (
    <Dot
      cx={cx}
      cy={cy}
      r={isHovered ? 6 : 4}
      stroke={stroke}
      strokeWidth={2}
      fill="white"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <animate
        attributeName="r"
        from="0"
        to={isHovered ? 6 : 4}
        dur="0.5s"
        fill="freeze"
      />
    </Dot>
  );
};

CustomDot.propTypes = {
  cx: PropTypes.number,
  cy: PropTypes.number,
  stroke: PropTypes.string,
};

// Helper to render AI trend insights as a bullet list with headings.
const renderTrendInsights = (insightText) => {
  const parseBulletPoints = (text) => {
    const bulletIcon = (
      <div className="w-3 h-3 bg-teal-500 rounded-full inline-block mr-2 flex-shrink-0" />
    );
    if (!text) return null;
    if (Array.isArray(text)) {
      return (
        <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
          {text.map((line, idx) => (
            <li key={idx} className="flex items-center">
              {bulletIcon}
              <span>{line}</span>
            </li>
          ))}
        </ul>
      );
    }
    const lines = text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line !== "");
    return (
      <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
        {lines.map((line, idx) => (
          <li key={idx} className="flex items-center">
            {bulletIcon}
            <span>{line}</span>
          </li>
        ))}
      </ul>
    );
  };

  try {
    const parsed = JSON.parse(insightText);
    if (
      parsed.ai_trend &&
      typeof parsed.ai_trend === "object" &&
      !Array.isArray(parsed.ai_trend)
    ) {
      const { observations, recommendations } = parsed.ai_trend;
      return (
        <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left">
          <h4 className="text-2xl font-bold text-gray-900 mb-4">
            <Cpu className="w-6 h-6 text-teal-500 inline-block mr-2" />
            Trend Insights
          </h4>
          <div className="grid grid-cols-1 gap-6">
            {observations && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Observations
                </h5>
                {parseBulletPoints(observations)}
              </div>
            )}
            {recommendations && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Recommendations
                </h5>
                {parseBulletPoints(recommendations)}
              </div>
            )}
          </div>
        </div>
      );
    }
    if (parsed.observations || parsed.recommendations) {
      return (
        <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left">
          <h4 className="text-2xl font-bold text-gray-900 mb-4">
            <Cpu className="w-6 h-6 text-teal-500 inline-block mr-2" />
            Trend Insights
          </h4>
          <div className="grid grid-cols-1 gap-6">
            {parsed.observations && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Observations
                </h5>
                {parseBulletPoints(parsed.observations)}
              </div>
            )}
            {parsed.recommendations && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Recommendations
                </h5>
                {parseBulletPoints(parsed.recommendations)}
              </div>
            )}
          </div>
        </div>
      );
    }
    if (parsed.ai_trend && Array.isArray(parsed.ai_trend)) {
      const trendLines = [];
      const recLines = [];
      let recStarted = false;
      parsed.ai_trend.forEach((line) => {
        const clean = line.replace(/[{}]/g, "").trim();
        if (clean.toLowerCase().includes("recommendations:")) {
          recStarted = true;
          recLines.push(clean.replace(/recommendations:/i, "").trim());
        } else if (recStarted) {
          recLines.push(clean);
        } else {
          trendLines.push(clean);
        }
      });
      return (
        <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left">
          <h4 className="text-2xl font-bold text-gray-900 mb-4">
            <Cpu className="w-6 h-6 text-teal-500 inline-block mr-2" />
            Trend Insights
          </h4>
          <div className="grid grid-cols-1 gap-6">
            {trendLines.length > 0 && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Observations
                </h5>
                <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
                  {trendLines.map((line, index) => (
                    <li key={index} className="flex items-center">
                      <Cpu className="w-4 h-4 text-teal-500 inline-block mr-2 flex-shrink-0" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {recLines.length > 0 && (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
                <h5 className="text-lg font-medium text-teal-600 border-b border-gray-200 pb-1 mb-3">
                  <Cpu className="w-5 h-5 text-teal-500 inline-block mr-2" />
                  Recommendations
                </h5>
                <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
                  {recLines.map((line, index) => (
                    <li key={index} className="flex items-center">
                      <Cpu className="w-4 h-4 text-teal-500 inline-block mr-2 flex-shrink-0" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      );
    }
    if (Array.isArray(parsed)) {
      return (
        <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left">
          <h4 className="text-2xl font-bold text-gray-900 mb-4">
            <Cpu className="w-6 h-6 text-teal-500 inline-block mr-2" />
            Trend Insights
          </h4>
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
            <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
              {parsed
                .filter((line) => line.trim() !== "")
                .map((line, index) => (
                  <li key={index} className="flex items-center">
                    <Cpu className="w-4 h-4 text-teal-500 inline-block mr-2 flex-shrink-0" />
                    <span>{line.trim()}</span>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      );
    }
  } catch (error) {
    console.log(error);
    return (
      
      
      <div className="bg-white shadow-md rounded-lg p-8 border border-gray-200 transition-transform transform hover:scale-105 hover:shadow-xl text-left">
        <h4 className="text-2xl font-bold text-gray-900 mb-4">
          <Cpu className="w-6 h-6 text-teal-500 inline-block mr-2" />
          Trend Insights
        </h4>
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 shadow-sm">
          <ul className="list-disc pl-5 text-gray-800 text-sm text-left">
            {insightText
              .split("\n")
              .filter((line) => line.trim() !== "")
              .map((line, index) => (
                <li key={index} className="flex items-center">
                  <Cpu className="w-4 h-4 text-teal-500 inline-block mr-2 flex-shrink-0" />
                  <span>{line.trim()}</span>
                </li>
              ))}
          </ul>
        </div>
      </div>
    );
  }
  return null;
};

const FailureTrendsGraph = ({ motor, months }) => {
  const [data, setData] = useState([]);
  const [combinedData, setCombinedData] = useState([]);
  const [aiTrend, setAiTrend] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (motor) {
      getFailureTrends(motor, months).then((response) => {
        setData(response.data || []);
        if (response.trend_analysis) {
          const originalData = response.data;
          const regressionData =
            (response.trend_analysis.regression &&
              response.trend_analysis.regression.predicted) ||
            [];
          const movingAvgData = response.trend_analysis.moving_average || [];
          const merged = originalData.map((item) => {
            const regItem =
              regressionData.find((r) => r.month === item.month) || {};
            const movItem =
              movingAvgData.find((m) => m.month === item.month) || {};
            return {
              month: item.month,
              count: item.count,
              predicted_count: regItem.predicted_count || null,
              moving_avg: movItem.moving_avg || null,
            };
          });
          setCombinedData(merged);
        }
        if (response.ai_trend_insight && response.ai_trend_insight.trim()) {
          setAiTrend(response.ai_trend_insight);
        } else {
          setAiTrend(
            JSON.stringify({ ai_trend: ["No trend insights available."] })
          );
        }
        setLoading(false);
      });
    }
  }, [motor, months]);

  if (loading) return <LoadingSpinner />;
  if ((!data || data.length === 0) && (!combinedData || combinedData.length === 0))
    return <p className="text-center text-gray-800">No data found</p>;

  return (
    <div className="bg-white p-6 rounded-md shadow-md">
      <h2 className="text-xl font-bold mb-4">Motor Failure Trends</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={combinedData.length ? combinedData : data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <RechartLegend verticalAlign="top" height={36} />
          <Line
            type="monotone"
            dataKey="count"
            name="Failure Count"
            stroke="#8884d8"
            strokeWidth={2}
            activeDot={{ r: 8 }}
            dot={<CustomDot stroke="#8884d8" />}
          />
          {combinedData.length > 0 &&
            combinedData.some((d) => d.predicted_count !== null) && (
              <Line
                type="monotone"
                dataKey="predicted_count"
                name="Regression Trend"
                stroke="#FF0000"
                strokeWidth={2}
                strokeDasharray="5 5"
              />
            )}
          {combinedData.length > 0 &&
            combinedData.some((d) => d.moving_avg !== null) && (
              <Line
                type="monotone"
                dataKey="moving_avg"
                name="Moving Average"
                stroke="#00AA00"
                strokeWidth={2}
                strokeDasharray="3 3"
              />
            )}
        </LineChart>
      </ResponsiveContainer>
      {aiTrend && (
        <div className="mt-4">
          {renderTrendInsights(aiTrend)}
        </div>
      )}
    </div>
  );
};

FailureTrendsGraph.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

const VerticalBar = (props) => {
  const { x, y, width, height, fill } = props;
  return (
    <rect x={x} y={y} width={width} height={height} fill={fill}>
      <animateTransform
        attributeName="transform"
        type="translate"
        from={`0,${height}`}
        to="0,0"
        dur="1.5s"
        fill="freeze"
      />
    </rect>
  );
};

const RpmVsLoadGraph = ({ motor, months }) => {
  const [data, setData] = useState([]);
  const [aiTrend, setAiTrend] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = () => {
    getRpmVsLoad(motor, months)
      .then((response) => {
        const rawData = response.data || [];
        const aggregatedData = rawData.map((item) => ({
          month: item?.Month || "Unknown",
          avgRpm: item?.avg_rpm || 0,
          avgLoad: item?.avg_load || 0,
        }));
        setData(aggregatedData);
        if (response.ai_trend_insight && response.ai_trend_insight.trim()) {
          setAiTrend(response.ai_trend_insight);
        } else {
          setAiTrend(
            JSON.stringify({ ai_trend: ["No trend insights available."] })
          );
        }
        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching RPM vs Load data:", error);
        setLoading(false);
      });
  };

  useEffect(() => {
    if (motor) {
      fetchData();
    }
  }, [motor, months]);

  if (loading) return <LoadingSpinner />;
  if (!data || data.length === 0) {
    return <p className="text-center text-gray-800">No data found</p>;
  }

  return (
    <div className="bg-white p-6 rounded-md shadow-md">
      <h2 className="text-xl font-bold mb-4">
        Monthly Aggregated RPM vs. Load
      </h2>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart
          data={data}
          margin={{ top: 20, right: 50, left: 20, bottom: 20 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="month"
            label={{
              value: "Month",
              position: "insideBottom",
              offset: -10,
              style: { fontSize: 14, fill: "#666" },
            }}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            yAxisId="left"
            label={{
              value: "Avg RPM",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 14, fill: "#666" },
            }}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            label={{
              value: "Avg Load (%)",
              angle: 90,
              position: "insideRight",
              style: { fontSize: 14, fill: "#666" },
            }}
            tick={{ fontSize: 12 }}
          />
          <Tooltip />
          <RechartLegend verticalAlign="top" height={36} />
          <Bar
            yAxisId="left"
            dataKey="avgRpm"
            name="Average RPM"
            fill="#8884d8"
            barSize={20}
            shape={<VerticalBar />}
          />
          <Bar
            yAxisId="right"
            dataKey="avgLoad"
            name="Average Load (%)"
            fill="#82ca9d"
            barSize={20}
          />
        </BarChart>
      </ResponsiveContainer>
      {aiTrend && (
        <div className="mt-4">
          {renderTrendInsights(aiTrend)}
        </div>
      )}
    </div>
  );
};

RpmVsLoadGraph.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

const renderCustomXDot = (props) => {
  const { cx, cy, fill } = props;
  return (
    <svg x={cx - 6} y={cy - 6} width={12} height={12} viewBox="0 0 12 12">
      <line x1="0" y1="0" x2="12" y2="12" stroke={fill} strokeWidth="2" />
      <line x1="12" y1="0" x2="0" y2="12" stroke={fill} strokeWidth="2" />
    </svg>
  );
};

const TempVsVibration = ({ motor, months }) => {
  const [groupedData, setGroupedData] = useState({});
  const [, setCorrelation] = useState(null);
  const [aiTrend, setAiTrend] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (motor) {
      getTempVsVibration(motor, months).then((response) => {
        const formattedData = (response.data || []).map((item) => ({
          temperature: item["Temperature (°C)"],
          vibration: item["Vibration (mm/s)"],
          status: item["Status"] || "Unknown",
        }));
        const groups = formattedData.reduce((acc, item) => {
          const key = item.status;
          if (!acc[key]) acc[key] = [];
          acc[key].push(item);
          return acc;
        }, {});
        setGroupedData(groups);
        if (response.ai_trend_insight && response.ai_trend_insight.trim()) {
          setAiTrend(response.ai_trend_insight);
        } else {
          setAiTrend(
            JSON.stringify({ ai_trend: ["No trend insights available."] })
          );
        }
        setCorrelation(
          response.statistics ? response.statistics.correlation : null
        );
        setLoading(false);
      });
    }
  }, [motor, months]);

  if (loading) return <LoadingSpinner />;
  if (Object.keys(groupedData).length === 0) {
    return <p className="text-center text-gray-800">No data found</p>;
  }

  const statusColors = {
    "High Vibration": "#8884d8",
    Overload: "#ffb347",
    Running: "#a2d39c",
    Shutdown: "#ddddd0",
  };

  return (
    <div className="bg-white p-6 rounded-md shadow-md">
      <h2 className="text-xl font-bold mb-4">Temperature vs Vibration</h2>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="temperature"
            name="Temperature (°C)"
            domain={[35, "auto"]}
            ticks={[35, 40, 45, 50, 55, 60, 65, 70]}
            tick={{ fontSize: 12 }}
            label={{
              value: "Temperature (°C)",
              position: "insideBottom",
              offset: -10,
            }}
          />
          <YAxis
            type="number"
            dataKey="vibration"
            name="Vibration (mm/s)"
            domain={[0, 7]}
            ticks={[0, 1, 2, 3, 4, 5, 6, 7]}
            tick={{ fontSize: 12 }}
            label={{
              value: "Vibration (mm/s)",
              angle: -90,
              position: "insideLeft",
            }}
          />
          <Tooltip
            formatter={(value, name) => {
              if (name === "temperature")
                return [value, "Temperature (°C)"];
              if (name === "vibration")
                return [value, "Vibration (mm/s)"];
              return [value, name];
            }}
          />
          <RechartLegend verticalAlign="top" height={36} />
          {Object.keys(groupedData).map((status) => (
            <Scatter
              key={status}
              name={status}
              data={groupedData[status]}
              fill={statusColors[status] || "#000000"}
              shape={renderCustomXDot}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
      {aiTrend && (
        <div className="mt-4">
          {renderTrendInsights(aiTrend)}
        </div>
      )}
    </div>
  );
};

TempVsVibration.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

const TrendAnalysisView = ({ motor, months }) => {
  const views = [
    { key: "failure", label: "Failure Trends" },
    { key: "rpmLoad", label: "RPM vs. Load" },
    { key: "tempVibration", label: "Temp vs. Vibration" },
  ];

  const viewIcons = {
    failure: <AlertCircle className="w-6 h-6 text-teal-500" />,
    rpmLoad: <TrendingUp className="w-6 h-6 text-teal-500" />,
    tempVibration: <Sun className="w-6 h-6 text-teal-500" />,
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-center mb-10 bg-gradient-to-r from-blue-50 to-blue-100 p-8 rounded-lg shadow-lg">
        <ChartBar className="w-12 h-12 text-teal-500 mr-4 animate-pulse" />
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900">
          Trend Analysis for Motor {motor} over the past {months}{" "}
          {months > 1 ? "months" : "month"}
        </h2>
      </div>

      {/* Tabs with animated transitions */}
      <Tab.Group>
        <Tab.List className="flex flex-wrap gap-4 mb-8">
          {views.map((view) => (
            <Tab
              key={view.key}
              className={({ selected }) =>
                `px-5 py-2 rounded-md border transition-all duration-200 focus:outline-none ${
                  selected
                    ? "bg-teal-500 border-teal-500 scale-105"
                    : "bg-white border-gray-300 hover:scale-105"
                } text-black`
              }
            >
              <div className="flex items-center">
                {viewIcons[view.key]}
                <span className="ml-2">{view.label}</span>
              </div>
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels>
          {views.map((view) => (
            <Tab.Panel
              key={view.key}
              className="p-4 border border-gray-300 rounded-md"
            >
              <Transition
                show={true}
                as="div"
                enter="transition-opacity duration-300"
                enterFrom="opacity-0"
                enterTo="opacity-100"
                leave="transition-opacity duration-300"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
              >
                {view.key === "failure" ? (
                  <FailureTrendsGraph motor={motor} months={months} />
                ) : view.key === "rpmLoad" ? (
                  <RpmVsLoadGraph motor={motor} months={months} />
                ) : view.key === "tempVibration" ? (
                  <TempVsVibration motor={motor} months={months} />
                ) : (
                  <div>
                    <h3 className="text-2xl font-semibold mb-2 text-black">
                      {view.label} View
                    </h3>
                    <p className="text-black">
                      This is a placeholder for the {view.label} view.
                    </p>
                  </div>
                )}
              </Transition>
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
};

TrendAnalysisView.propTypes = {
  motor: PropTypes.string.isRequired,
  months: PropTypes.number.isRequired,
};

export default TrendAnalysisView;
