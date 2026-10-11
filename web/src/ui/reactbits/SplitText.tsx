// SplitText from React Bits (reactbits.dev, SplitText-TS-CSS). Local changes: reduced motion keeps the plain text,
// and the text-align default is left. Characters rise in once when the text scrolls into view.
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText as GSAPSplitText } from "gsap/SplitText";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { prefersReducedMotion } from "../motion.ts";

gsap.registerPlugin(ScrollTrigger, GSAPSplitText, useGSAP);

export interface SplitTextProps {
  text: string;
  className?: string;
  delay?: number;
  duration?: number;
  ease?: string | ((t: number) => number);
  splitType?: "chars" | "words" | "lines" | "words, chars";
  from?: gsap.TweenVars;
  to?: gsap.TweenVars;
  threshold?: number;
  rootMargin?: string;
  tag?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "span";
  textAlign?: CSSProperties["textAlign"];
}

export default function SplitText({
  text,
  className = "",
  delay = 50,
  duration = 1.25,
  ease = "power3.out",
  splitType = "chars",
  from = { opacity: 0, y: 40 },
  to = { opacity: 1, y: 0 },
  threshold = 0.1,
  rootMargin = "-100px",
  textAlign = "left",
  tag = "p",
}: SplitTextProps) {
  const ref = useRef<HTMLElement>(null);
  const done = useRef(false);
  const [fontsLoaded, setFontsLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    document.fonts.ready.then(() => { if (live) setFontsLoaded(true); });
    return () => { live = false; };
  }, []);

  useGSAP(
    () => {
      const el = ref.current;
      if (!el || !text || !fontsLoaded || done.current || prefersReducedMotion()) return;
      const startPct = (1 - threshold) * 100;
      const margin = /^(-?\d+(?:\.\d+)?)(px|em|rem|%)?$/.exec(rootMargin);
      const value = margin ? parseFloat(margin[1]) : 0;
      const unit = margin ? margin[2] || "px" : "px";
      const sign = value === 0 ? "" : value < 0 ? `-=${Math.abs(value)}${unit}` : `+=${value}${unit}`;
      const split = new GSAPSplitText(el, {
        type: splitType,
        smartWrap: true,
        autoSplit: splitType === "lines",
        linesClass: "split-line",
        wordsClass: "split-word",
        charsClass: "split-char",
        reduceWhiteSpace: false,
        onSplit: (self: GSAPSplitText) => {
          const targets = (splitType.includes("chars") && self.chars.length ? self.chars
            : splitType.includes("words") && self.words.length ? self.words : self.lines);
          return gsap.fromTo(targets, { ...from }, {
            ...to,
            duration,
            ease,
            stagger: delay / 1000,
            scrollTrigger: { trigger: el, start: `top ${startPct}%${sign}`, once: true, fastScrollEnd: true },
            onComplete: () => { done.current = true; },
            willChange: "transform, opacity",
            force3D: true,
          });
        },
      });
      // useGSAP reverts the tween and its ScrollTrigger; the split DOM is restored here.
      return () => split.revert();
    },
    { dependencies: [text, delay, duration, ease, splitType, JSON.stringify(from), JSON.stringify(to), threshold, rootMargin, fontsLoaded], scope: ref },
  );

  const Tag = tag;
  return (
    <Tag ref={ref as never} className={`split-parent ${className}`}
      style={{ textAlign, overflow: "hidden", display: "inline-block", whiteSpace: "normal", overflowWrap: "break-word" }}>
      {text}
    </Tag>
  );
}
