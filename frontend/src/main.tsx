import "./index.css";

import { createRoot } from "react-dom/client";

import App from "./App.tsx";

// No <StrictMode>: its double-mounting attaches deck.gl's interleaved overlay to
// the MapLibre WebGL context twice ("WebGL context already attached to device").
createRoot(document.getElementById("root")!).render(<App />);
