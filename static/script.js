const charts = {};
const $ = (id) => document.getElementById(id);

function dateRange() {
  return { start: $("start").value, end: $("end").value };
}

function query(path) {
  const params = new URLSearchParams(dateRange());
  return fetch(`${path}?${params}`).then(async (response) => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The API request failed.");
    return data;
  });
}

function format(value, digits = 1) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(digits);
}

function showError(error) {
  $("notice").textContent = error.message;
  $("notice").hidden = false;
}

function drawChart(id, label, labels, data, color) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), {
    type: "line",
    data: { labels, datasets: [{ label, data, borderColor: color, backgroundColor: `${color}18`, fill: true, tension: .35, pointRadius: 1.5, borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 7, color: "#697873" } }, y: { grid: { color: "#e7ece9" }, ticks: { color: "#697873" } } } }
  });
}

async function refresh() {
  $("notice").hidden = true;
  const [metrics, hourly, sensors, performance] = await Promise.all([
    query("/api/metrics"), query("/api/hourly"), query("/api/sensors"), query("/api/performance")
  ]);
  $("avg-temperature").textContent = `${format(metrics.average_temperature)}°`;
  $("avg-humidity").textContent = `${format(metrics.average_humidity)}%`;
  $("temperature-range").textContent = `${format(metrics.minimum_temperature)}° / ${format(metrics.maximum_temperature)}°`;
  $("total-readings").textContent = Number(metrics.total_readings || 0).toLocaleString();
  const byHour = new Map();
  hourly.forEach((row) => {
    const key = row.bucket;
    const current = byHour.get(key) || { temperatures: [], humidities: [] };
    current.temperatures.push(Number(row.avg_temperature));
    current.humidities.push(Number(row.avg_humidity));
    byHour.set(key, current);
  });
  const labels = [...byHour.keys()].map((key) => new Date(key).toLocaleString([], { month: "short", day: "numeric", hour: "numeric" }));
  const average = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
  drawChart("temperature-chart", "Temperature", labels, [...byHour.values()].map((item) => average(item.temperatures)), "#f0643b");
  drawChart("humidity-chart", "Humidity", labels, [...byHour.values()].map((item) => average(item.humidities)), "#225bff");
  $("sensor-rows").innerHTML = sensors.map((sensor) => `<tr><td>${sensor.sensor_id}</td><td>${Number(sensor.reading_count).toLocaleString()}</td><td>${format(sensor.average_temperature)}°C</td><td>${format(sensor.average_humidity)}%</td><td>${new Date(sensor.last_reading).toLocaleString()}</td></tr>`).join("");
  $("raw-time").textContent = format(performance.raw_hypertable.execution_time_reported_ms);
  $("cagg-time").textContent = format(performance.continuous_aggregate.execution_time_reported_ms);
  $("raw-rows").textContent = `${Number(performance.raw_hypertable.rows_returned || 0).toLocaleString()} rows`;
  $("cagg-rows").textContent = `${Number(performance.continuous_aggregate.rows_returned || 0).toLocaleString()} rows`;
}

const end = new Date();
const start = new Date(end);
start.setDate(end.getDate() - 7);
$("start").value = start.toISOString().slice(0, 10);
$("end").value = end.toISOString().slice(0, 10);
$("range-form").addEventListener("submit", (event) => { event.preventDefault(); refresh().catch(showError); });
refresh().catch(showError);
