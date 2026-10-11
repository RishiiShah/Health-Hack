// AnimatedContent from React Bits (reactbits.dev, AnimatedContent-TS-CSS), trimmed to the options this app uses.
// Local changes: reduced motion shows the content at once; the disappear and custom-scroller options are removed.
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef, type HTMLAttributes, type ReactNode } from "react";
import { prefersReducedMotion } from "../motion.ts";

gsap.registerPlugin(ScrollTrigger);

interface AnimatedContentProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  distance?: number;
  direction?: "vertical" | "horizontal";
  reverse?: boolean;
  duration?: number;
  ease?: string;
  initialOpacity?: number;
  scale?: number;
  threshold?: number;
  delay?: number;
}

export default function AnimatedContent({
  children,
  distance = 100,
  direction = "vertical",
  reverse = false,
  duration = 0.8,
  ease = "power3.out",
  initialOpacity = 0,
  scale = 1,
  threshold = 0.1,
  delay = 0,
  style,
  ...props
}: AnimatedContentProps) {
  const ref = useRef<HTMLDivElement>(null);
  const still = prefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || still) return;
    const axis = direction === "horizontal" ? "x" : "y";
    gsap.set(el, { [axis]: reverse ? -distance : distance, scale, opacity: initialOpacity, visibility: "visible" });
    const tween = gsap.to(el, { [axis]: 0, scale: 1, opacity: 1, duration, ease, delay, paused: true });
    const trigger = ScrollTrigger.create({ trigger: el, start: `top ${(1 - threshold) * 100}%`, once: true, onEnter: () => tween.play() });
    return () => {
      trigger.kill();
      tween.kill();
      gsap.set(el, { clearProps: "transform,opacity,visibility" });
    };
  }, [still, distance, direction, reverse, duration, ease, initialOpacity, scale, threshold, delay]);

  return <div ref={ref} style={still ? style : { visibility: "hidden", ...style }} {...props}>{children}</div>;
}
