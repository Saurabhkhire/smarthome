import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./App.css";

/* StrictMode double-mounts effects and breaks Leaflet ("Map container is already initialized") in dev */
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
