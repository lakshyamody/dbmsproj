/**
 * Top bar: wordmark on the left, section nav in the middle, and the link out to
 * the live dashboard on the right. Hides on scroll down, returns on scroll up.
 */
import { useRef, useState } from "react"
import { Menu } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList,
} from "@/components/ui/navigation-menu"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Wordmark } from "@/components/brand/Brand"
import { gsap, useGSAP, ScrollTrigger } from "@/lib/gsap"
import { scrollToId } from "@/lib/lenis"
import { DASHBOARD_URL } from "@/lib/config"

const NAV = [
  { id: "mission", label: "Mission" },
  { id: "challenge", label: "Challenge" },
  { id: "payloads", label: "Payloads" },
  { id: "decides", label: "How it decides" },
  { id: "network", label: "Network" },
  { id: "team", label: "Team" },
]

export function TopBar() {
  const bar = useRef<HTMLElement>(null)
  const [open, setOpen] = useState(false)

  useGSAP(
    () => {
      const el = bar.current
      if (!el) return

      gsap.set(el, { yPercent: 0 })
      const show = gsap.quickTo(el, "yPercent", { duration: 0.4, ease: "power3.out" })

      let last = 0
      const st = ScrollTrigger.create({
        start: 0,
        end: "max",
        onUpdate: (self) => {
          const y = self.scroll()
          // Always visible at the very top of the page.
          if (y < 80) {
            show(0)
            el.dataset.solid = "false"
          } else {
            el.dataset.solid = "true"
            show(y > last ? -140 : 0)
          }
          last = y
        },
      })
      return () => st.kill()
    },
    { scope: bar }
  )

  const go = (id: string) => {
    setOpen(false)
    scrollToId(id)
  }

  return (
    <header
      ref={bar}
      data-solid="false"
      className="fixed inset-x-0 top-0 z-50 transition-colors duration-300 data-[solid=true]:border-b data-[solid=true]:border-white/[0.12] data-[solid=true]:bg-black/70 data-[solid=true]:backdrop-blur-xl"
    >
      <div className="shell flex h-16 items-center justify-between gap-6 md:h-[72px]">
        <button
          onClick={() => scrollToId("hero")}
          className="group flex items-center gap-2 text-[17px] tracking-[-0.02em] text-white"
          aria-label="SomaiyaSat — back to top"
        >
          <Wordmark glyphClassName="text-white transition-transform duration-500 group-hover:rotate-180" />
        </button>

        <NavigationMenu className="hidden lg:flex">
          <NavigationMenuList className="gap-1">
            {NAV.map((n) => (
              <NavigationMenuItem key={n.id}>
                <button
                  onClick={() => go(n.id)}
                  className="mono-label rounded-[8px] px-3 py-2 text-[#8a8f98] transition-colors hover:bg-white/[0.06] hover:text-white"
                >
                  {n.label}
                </button>
              </NavigationMenuItem>
            ))}
          </NavigationMenuList>
        </NavigationMenu>

        <div className="flex items-center gap-2">
          <Button
            asChild
            variant="outline"
            size="sm"
            className="mono-label hidden sm:inline-flex"
          >
            <a href={DASHBOARD_URL} target="_blank" rel="noreferrer">
              Mission Control →
            </a>
          </Button>

          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild className="lg:hidden">
              <Button variant="ghost" size="icon" aria-label="Open menu">
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[82vw] max-w-sm border-l">
              <SheetHeader>
                <SheetTitle className="text-left">
                  <Wordmark className="text-[19px]" />
                </SheetTitle>
              </SheetHeader>
              <nav className="mt-8 flex flex-col gap-1 px-4">
                {NAV.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => go(n.id)}
                    className="border-b border-white/[0.08] py-4 text-left text-lg text-white/90 transition-colors hover:text-white"
                  >
                    {n.label}
                  </button>
                ))}
              </nav>
              <div className="mt-8 px-4">
                <Button asChild className="mono-label w-full">
                  <a href={DASHBOARD_URL} target="_blank" rel="noreferrer">
                    Mission Control →
                  </a>
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  )
}
