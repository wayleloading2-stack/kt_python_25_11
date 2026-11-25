import { useEffect, useState } from "react";

const CURRENCIES = ["USD", "GBP", "CHF", "JPY", "CAD"];

export default function App() {
  const [status, setStatus] = useState("Подключение...");
  const [rates, setRates] = useState(null); 
  const [error, setError] = useState(null);
  const [interval, setInterval] = useState("5");
  const validInterval = /^\d+$/.test(interval) && Number(interval) >= 1 && Number(interval) <= 60;

  useEffect(() => {
    const eventSource = new EventSource("/events");

    eventSource.onopen = () => {
      setStatus("Подключено к SSE");
      setError(null);
    };

    eventSource.addEventListener("currency_update", (event) => {
      setRates(JSON.parse(event.data));
      setStatus("Подключено к SSE");
      setError(null);
    });

    eventSource.addEventListener("error", (event) => {
      if (event.data) setError(JSON.parse(event.data).message);
    });

    eventSource.onerror = () => {
      setStatus("Нет соединения");
      setError("Соединение потеряно. Переподключение...");
    };

    return () => eventSource.close();
  }, []);

  return (
    <div className="page">
      <h1>Курсы валют</h1>
      <p className={error ? "status status--error" : "status"}>{status}</p>
      {error && <p className="error" role="alert">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Валюта</th>
            <th>Курс к EUR</th>
          </tr>
        </thead>
        <tbody>
          {CURRENCIES.map((c) => (
            <tr key={c}>
              <td>{c}</td>
              <td>{rates?.rates?.[c] ?? "--"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="export-controls">
        <label htmlFor="interval">Интервал (сек.):</label>
        <input
          id="interval"
          type="number"
          min="1"
          max="60"
          step="1"
          value={interval}
          onChange={(event) => setInterval(event.target.value)}
        />
        {validInterval ? (
          <a className="download-button" href={`/export?interval=${Number(interval)}`} download="rates.csv">
            Скачать CSV
          </a>
        ) : (
          <button className="download-button" disabled>Скачать CSV</button>
        )}
      </div>
      {!validInterval && <p className="error">Введите целое число от 1 до 60.</p>}

      <p>
        Последнее обновление:{" "}
        {rates?.updated_at ? new Date(rates.updated_at).toLocaleTimeString() : "--"}
      </p>
    </div>
  );
}
