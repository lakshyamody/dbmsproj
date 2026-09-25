import { useCallback, useState } from "react"

import { IntroGate } from "@/components/layout/IntroGate"
import { TopBar } from "@/components/layout/TopBar"
import { SideTab } from "@/components/layout/SideTab"
import { CursorReadout } from "@/components/layout/CursorReadout"
import { GlitchBands } from "@/components/layout/GlitchBands"
import { ProgressRail } from "@/components/layout/ProgressRail"
import { Footer } from "@/components/layout/Footer"
import { Hero } from "@/sections/Hero"
import { Mission } from "@/sections/Mission"
import { Challenge } from "@/sections/Challenge"
import { Payloads } from "@/sections/Payloads"
import { Build } from "@/sections/Build"
import { HowItDecides } from "@/sections/HowItDecides"
import { ByTheNumbers } from "@/sections/ByTheNumbers"
import { GroundNetwork } from "@/sections/GroundNetwork"
import { Team } from "@/sections/Team"
import { CTA } from "@/sections/CTA"
import { useStats } from "@/hooks/useStats"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function App() {
  const [ready, setReady] = useState(false)
  const { stats } = useStats()

  // Stable identity: IntroGate's effect must not re-run when useStats resolves.
  const handleIntroDone = useCallback(() => setReady(true), [])

  return (
    <TooltipProvider delayDuration={120}>
      <IntroGate onDone={handleIntroDone} />
      <TopBar />
      <SideTab />
      <CursorReadout />
      <GlitchBands />
      <ProgressRail ready={ready} />

      <main>
        <Hero ready={ready} />
        <Mission />
        <Challenge />
        <Payloads stats={stats} />
        <Build />
        <HowItDecides />
        <ByTheNumbers stats={stats} />
        <GroundNetwork stats={stats} />
        <Team />
        <CTA />
      </main>

      <Footer />
    </TooltipProvider>
  )
}
