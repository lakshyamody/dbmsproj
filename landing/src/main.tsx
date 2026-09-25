import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import "@/lib/gsap"
import { initLenis } from "@/lib/lenis"
import App from "./App"

initLenis()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
