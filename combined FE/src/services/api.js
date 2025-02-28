import axios from "axios";
 
// Updated base URL to include the '/api' prefix
const baseUrl = import.meta.env.VITE_BASE_URL;
 
// Get list of motor IDs
export const getMotorIds = async () => {
  const response = await axios.get(`${baseUrl}/api/motor-ids`);
  return response.data;
};
 
// Get failure trends for a given motor and a number of months
export const getFailureTrends = async (motor_id, months) => {
  const response = await axios.get(
    `${baseUrl}/api/failure-trends?motor_id=${motor_id}&months=${months}`
  );
  return response.data;
};
 
// Get RPM vs Load analytics for a given motor and a number of months
export const getRpmVsLoad = async (motor_id, months) => {
  const response = await axios.get(
    `${baseUrl}/api/rpm-vs-load?motor_id=${motor_id}&months=${months}`
  );
  return response.data;
};
 
// Get Temperature vs Vibration analytics for a given motor and a number of months
export const getTempVsVibration = async (motor_id, months) => {
  const response = await axios.get(
    `${baseUrl}/api/temp-vs-vibration?motor_id=${motor_id}&months=${months}`
  );
  return response.data;
};