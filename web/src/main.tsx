import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Cascade order: tokens and base first, then each component's stylesheet (pulled in by App), then motion last.
import "./styles/tokens.css";
import "./styles/base.css";
import App from "./App.tsx";
import "./styles/motion.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
