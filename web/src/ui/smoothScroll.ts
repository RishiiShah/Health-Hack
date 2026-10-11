// Lenis smooth scrolling for the window. GSAP's ticker drives it, so ScrollTrigger reads the same scroll position.
// Lenis turns itself off for reduced motion; nested scroll areas (tables, panels) keep their native scrolling.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { useEffect } from "react";

gsap.registerPlugin(ScrollTrigger);

let active: Lenis | null = null;

export function useSmoothScroll() {
  useEffect(() => {
    const lenis = new Lenis({ allowNestedScroll: true });
    const tick = (seconds: number) => lenis.raf(seconds * 1000);
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    active = lenis;
    return () => {
      gsap.ticker.remove(tick);
      gsap.ticker.lagSmoothing(500, 33);
      lenis.destroy();
      if (active === lenis) active = null;
    };
  }, []);
}

// In-page links: glide with Lenis when it runs, otherwise jump. The URL hash is left alone (it routes app pages).
export function scrollToSection(id: string) {
  const target = document.getElementById(id);
  if (!target) return;
  if (active) active.scrollTo(target);
  else target.scrollIntoView();
}
