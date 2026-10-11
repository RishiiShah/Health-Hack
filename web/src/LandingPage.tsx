import React from "react";

type Role = "coordinator" | "lead" | "physician";

interface LandingPageProps {
  onEnter: (role: Role) => void;
  onGoToSignIn: (role?: Role) => void;
}

const TABS = [
  { id: "overview" as const, label: "Overview" },
  { id: "network" as const, label: "Network" },
  { id: "roles" as const, label: "Workspaces" },
  { id: "safety" as const, label: "Clinical Proof" },
];

export const LandingPage: React.FC<LandingPageProps> = ({ onGoToSignIn }) => {
  const [activeTab, setActiveTab] = React.useState<"overview" | "network" | "roles" | "safety">("overview");
  const tabRefs = React.useRef<Record<string, HTMLButtonElement | null>>({});
  const [pillStyle, setPillStyle] = React.useState<{ left: number; width: number }>({ left: 4, width: 76 });
  const isClickScrolling = React.useRef(false);
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);

  // Smooth sliding pill positioning
  const updatePill = React.useCallback(() => {
    const currentTabEl = tabRefs.current[activeTab];
    if (currentTabEl) {
      setPillStyle({
        left: currentTabEl.offsetLeft,
        width: currentTabEl.offsetWidth,
      });
    }
  }, [activeTab]);

  React.useLayoutEffect(() => {
    updatePill();
  }, [updatePill]);

  React.useEffect(() => {
    window.addEventListener("resize", updatePill);
    return () => window.removeEventListener("resize", updatePill);
  }, [updatePill]);

  // Seamless map keyer: dynamically keys out off-white paper pixels around the US landmass
  // so the topographic terrain floats directly onto the smoky slate background with zero rectangular box
  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const img = new Image();
    img.src = "/us_network_map.jpg";
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(img, 0, 0);

      try {
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const d = imgData.data;
        const bgR = d[0], bgG = d[1], bgB = d[2];

        for (let i = 0; i < d.length; i += 4) {
          const r = d[i], g = d[i + 1], b = d[i + 2];
          const dr = r - bgR, dg = g - bgG, db = b - bgB;
          const dist = Math.sqrt(dr * dr + dg * dg + db * db);

          if (dist < 18) {
            d[i + 3] = 0;
          } else if (dist < 45) {
            d[i + 3] = Math.round(((dist - 18) / 27) * 255);
          }
        }
        ctx.putImageData(imgData, 0, 0);
      } catch {
        // Fallback if cross-origin or local canvas restrictions apply
      }
    };
  }, []);

  // Smooth scroll spy (60fps rAF with click-scroll lock to prevent lag/stutter)
  React.useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (isClickScrolling.current) return;

      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollY = window.scrollY;
          const networkEl = document.getElementById("network");
          const rolesEl = document.getElementById("roles");
          const safetyEl = document.getElementById("safety");

          const safetyTop = safetyEl ? safetyEl.offsetTop - 260 : Infinity;
          const rolesTop = rolesEl ? rolesEl.offsetTop - 260 : Infinity;
          const networkTop = networkEl ? networkEl.offsetTop - 260 : Infinity;

          if (scrollY >= safetyTop) {
            setActiveTab("safety");
          } else if (scrollY >= rolesTop) {
            setActiveTab("roles");
          } else if (scrollY >= networkTop) {
            setActiveTab("network");
          } else {
            setActiveTab("overview");
          }
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id: "overview" | "network" | "roles" | "safety") => {
    setActiveTab(id);
    isClickScrolling.current = true;
    if (id === "overview") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
    setTimeout(() => {
      isClickScrolling.current = false;
    }, 750);
  };

  return (
    <div className="min-h-screen bg-[#28323D] text-[#F5F3ED] overflow-x-hidden selection:bg-[#B8D8EB] selection:text-[#101B2B] flex flex-col justify-between">
      <style>{`
        /* Floating Glass Cards */
        @keyframes floatCard1 {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-7px); }
        }
        @keyframes floatCard2 {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(6px); }
        }
        .anim-float-1 { animation: floatCard1 4.5s ease-in-out infinite; }
        .anim-float-2 { animation: floatCard2 5s ease-in-out infinite; }

        /* Card Hover Lift */
        .hover-lift {
          transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.35s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.35s ease;
        }
        .hover-lift:hover {
          transform: translateY(-5px);
          box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.45);
        }
      `}</style>

      {/* ================= STATIC MATTE SMOKY SLATE BACKGROUND ================= */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden bg-[#28323D]">
        {/* Broad subtle radial gradient behind the map */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 85% 75% at 50% 520px, #364550 0%, #2D3945 55%, #28323D 100%)",
          }}
        />
      </div>

      {/* ================= 1. FLOATING PILL NAVBAR ================= */}
      <nav className="fixed top-5 inset-x-0 mx-auto z-50 flex w-[calc(100%-48px)] max-w-5xl items-center justify-between rounded-full border border-[#E4E3DF]/80 bg-[#F1F0EC] px-6 py-2.5 backdrop-blur-xl shadow-[0_12px_36px_rgba(0,0,0,0.35)]">
        <button onClick={() => scrollTo("overview")} className="flex items-center gap-2 cursor-pointer select-none">
          <svg width="24" height="20" viewBox="0 0 24 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="2" width="11" height="11" rx="2.5" transform="rotate(-6 2 2)" fill="#82B4D2" fillOpacity="0.9" />
            <rect x="9" y="5" width="12" height="12" rx="2.5" transform="rotate(-6 9 5)" fill="#101B2B" />
          </svg>
          <strong className="text-base font-bold tracking-tight text-[#101B2B]">overlap</strong>
        </button>

        {/* Dynamic Center Navigation Tabs with Smooth Sliding Pill */}
        <div className="relative hidden md:flex items-center bg-[#E5E3DC] p-1 rounded-full border border-[#D5D3CB] text-xs font-medium text-[#4D6072]">
          {/* Animated Sliding Background Capsule */}
          <span
            className="absolute top-1 bottom-1 bg-[#F1F0EC] rounded-full shadow-sm transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] pointer-events-none"
            style={{
              left: `${pillStyle.left}px`,
              width: `${pillStyle.width}px`,
              opacity: pillStyle.width > 0 ? 1 : 0,
            }}
          />

          {TABS.map((tab) => (
            <button
              key={tab.id}
              ref={(el) => { tabRefs.current[tab.id] = el; }}
              onClick={() => scrollTo(tab.id)}
              className={`relative z-10 px-4 py-1.5 rounded-full transition-colors duration-200 cursor-pointer ${
                activeTab === tab.id
                  ? "text-[#101B2B] font-semibold"
                  : "text-[#4D6072] hover:text-[#101B2B]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => onGoToSignIn("coordinator")}
          className="rounded-full bg-[#101B2B] px-5 py-2 text-xs font-semibold text-[#F1F0EC] shadow-sm transition hover:bg-[#1E2E42] cursor-pointer"
        >
          Sign In
        </button>
      </nav>

      {/* ================= 2. MAIN HERO SECTION ================= */}
      <main id="overview" className="relative w-full mx-auto px-4 sm:px-6 pt-32 pb-16 flex-1 flex flex-col items-center">

        {/* CENTERED HEADLINE */}
        <section className="text-center max-w-3xl mx-auto mb-8 px-4">
          <h1 className="text-4xl md:text-5xl lg:text-[58px] font-extrabold font-heading text-[#F5F3ED] tracking-[-0.025em] leading-[1.12]">
            Every hospital covered,<br />
            <span className="font-normal italic font-serif text-[#B8D8EB] text-[1.08em] mr-1">before</span> the gap opens.
          </h1>
          <p className="mt-4 text-base md:text-lg text-[#BCC9D2] max-w-xl mx-auto leading-relaxed">
            Autonomous tele-stroke scheduling and cross-timezone coverage across 100+ partner hospitals nationwide.
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-3.5">
            <button
              onClick={() => onGoToSignIn("coordinator")}
              className="rounded-full bg-[#B8D8EB] hover:bg-[#A6CEE4] active:scale-[0.98] px-7 py-3.5 text-xs font-semibold text-[#101B2B] shadow-[0_8px_20px_rgba(184,216,235,0.25)] transition flex items-center gap-1.5 cursor-pointer"
            >
              <span>Sign In to Command Center</span>
              <span className="text-sm leading-none">→</span>
            </button>
            <button
              onClick={() => onGoToSignIn("physician")}
              className="rounded-full border border-[#BCC9D2]/35 bg-transparent hover:bg-white/5 active:scale-[0.98] px-6 py-3.5 text-xs font-medium text-[#F5F3ED] transition cursor-pointer"
            >
              Sign In as Physician
            </button>
          </div>
        </section>

        {/* ================= THE LIVING TOPOGRAPHIC US NETWORK MAP (ALWAYS IN MOTION) ================= */}
        <div id="network" className="relative w-full max-w-5xl aspect-[16/9] min-h-[460px] md:min-h-[580px] flex items-center justify-center my-4 scroll-mt-28">
          {/* FLOATING GLASS CARD 1 (SEVARO REAL STAT: <45s) */}
          <div className="anim-float-1 absolute top-4 left-2 md:top-8 md:left-6 z-20 rounded-[18px] bg-[#F1F0EC] border border-[#E5E3DF] px-5 py-4 shadow-[0_18px_45px_rgba(0,0,0,0.35)] text-left min-w-[190px]">
            <div className="text-[11px] font-mono text-[#4D6072] uppercase tracking-wider font-semibold">Synapse AI Response</div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl md:text-4xl font-extrabold text-[#101B2B] font-heading whitespace-nowrap">&lt;&nbsp;45s</span>
              <span className="text-xs text-[#4D6072] font-medium whitespace-nowrap">door-to-neuro</span>
            </div>
          </div>

          {/* FLOATING GLASS CARD 2 (SEVARO REAL STAT: 100+) */}
          <div className="anim-float-2 absolute bottom-6 right-2 md:bottom-12 md:right-8 z-20 rounded-[18px] bg-[#F1F0EC] border border-[#E5E3DF] p-4 md:p-5 flex items-center gap-3.5 shadow-[0_18px_45px_rgba(0,0,0,0.35)] min-w-[200px] text-left">
            <span className="text-3xl md:text-4xl font-extrabold text-[#101B2B] font-heading whitespace-nowrap">100+</span>
            <div className="text-xs font-semibold text-[#101B2B] leading-snug whitespace-nowrap">
              Hospitals Served<br /><span className="text-[#4D6072] font-normal">Across the Nation</span>
            </div>
          </div>

          {/* BASE HIGH-RESOLUTION TOPOGRAPHIC TERRAIN RELIEF MAP WITH SEAMLESS BLEND */}
          <div className="relative w-full h-full flex items-center justify-center">
            <canvas
              ref={canvasRef}
              className="w-full h-full object-contain pointer-events-none select-none rounded-2xl"
            />

            {/* LIVING MOTION SVG OVERLAY: CONTINUOUSLY STREAMING COMETS & PULSES */}
            <svg viewBox="0 0 1376 768" className="absolute inset-0 w-full h-full pointer-events-auto" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="cyanBeam" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#14B8A6" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#2DD4BF" stopOpacity="1" />
                  <stop offset="100%" stopColor="#5EEAD4" stopOpacity="0.9" />
                </linearGradient>

                <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* ROUTING ARCS */}
              <path d="M 340 195 Q 500 330 695 545" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.75" />
              <path d="M 288 392 Q 420 340 565 395" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.75" />
              <path d="M 565 395 Q 640 450 695 545" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.75" />
              <path d="M 695 545 Q 770 430 838 355" fill="none" stroke="url(#cyanBeam)" strokeWidth="3" opacity="0.85" />
              <path d="M 838 355 Q 950 310 1050 345" fill="none" stroke="url(#cyanBeam)" strokeWidth="3" opacity="0.85" />
              <path d="M 695 545 Q 890 470 1050 345" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.7" />

              {/* GLOWING CYAN COMETS (CONTINUOUS MOTION ACROSS THE MAP) */}
              <circle r="6" fill="#5EEAD4" filter="url(#glow)">
                <animateMotion dur="2.8s" repeatCount="indefinite" path="M 340 195 Q 500 330 695 545" />
              </circle>
              <circle r="5" fill="#5EEAD4" filter="url(#glow)">
                <animateMotion dur="2.4s" repeatCount="indefinite" path="M 288 392 Q 420 340 565 395" />
              </circle>
              <circle r="5.5" fill="#5EEAD4" filter="url(#glow)">
                <animateMotion dur="2.2s" repeatCount="indefinite" path="M 695 545 Q 770 430 838 355" />
              </circle>
              <circle r="6" fill="#5EEAD4" filter="url(#glow)">
                <animateMotion dur="2.5s" repeatCount="indefinite" path="M 838 355 Q 950 310 1050 345" />
              </circle>
              <circle r="5" fill="#5EEAD4" filter="url(#glow)">
                <animateMotion dur="3s" begin="1.2s" repeatCount="indefinite" path="M 695 545 Q 890 470 1050 345" />
              </circle>

              {/* DALLAS CONTINUOUS EXPANDING AMBER PULSE RINGS */}
              <circle cx="695" cy="545" r="20" fill="rgba(245, 158, 11, 0.25)" stroke="#F59E0B" strokeWidth="2.5">
                <animate attributeName="r" from="20" to="90" dur="2.4s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="0.9" to="0" dur="2.4s" repeatCount="indefinite" />
              </circle>
              <circle cx="695" cy="545" r="30" fill="none" stroke="#F59E0B" strokeWidth="1.8">
                <animate attributeName="r" from="20" to="135" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="0.8" to="0" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
              </circle>
              <circle cx="695" cy="545" r="45" fill="none" stroke="#F59E0B" strokeWidth="1.2">
                <animate attributeName="r" from="20" to="180" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="0.6" to="0" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
              </circle>

              {/* PULSING CITY NODES */}
              <g transform="translate(340, 195)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#0D9488" stroke="#FFFFFF" strokeWidth="2" />
                <text x="18" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#F5F3ED">Seattle</text>
              </g>

              <g transform="translate(288, 392)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="0.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="0.5s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#0D9488" stroke="#FFFFFF" strokeWidth="2" />
                <text x="18" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#F5F3ED">San Francisco</text>
              </g>

              <g transform="translate(565, 395)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="1s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="1s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#0D9488" stroke="#FFFFFF" strokeWidth="2" />
                <text x="0" y="24" textAnchor="middle" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#F5F3ED">Denver</text>
              </g>

              <g transform="translate(838, 355)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="1.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="1.5s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#0D9488" stroke="#FFFFFF" strokeWidth="2" />
                <text x="0" y="24" textAnchor="middle" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#F5F3ED">Chicago</text>
              </g>

              <g transform="translate(1050, 345)">
                <circle cx="0" cy="0" r="16" fill="rgba(20, 184, 166, 0.3)">
                  <animate attributeName="r" values="8;18;8" dur="3s" begin="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="2s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="7" fill="#0D9488" stroke="#FFFFFF" strokeWidth="2" />
                <text x="20" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#F5F3ED">New York</text>
              </g>

              {/* DALLAS HUB & FIXED 280px CAPSULE PILL */}
              <g transform="translate(695, 545)" className="cursor-pointer">
                <circle cx="0" cy="0" r="9" fill="#D6A451" stroke="#FFFFFF" strokeWidth="2.5" />
                <text x="20" y="6" fontFamily="'IBM Plex Sans'" fontSize="17" fontWeight="800" fill="#F5F3ED">Dallas</text>

                <g transform="translate(0, -42)">
                  <rect x="-140" y="-15" width="280" height="30" rx="15" fill="#111827" stroke="#D6A451" strokeWidth="1.2" />
                  <polygon points="-6,15 0,21 6,15" fill="#111827" />
                  <text x="0" y="5" textAnchor="middle" fontFamily="'IBM Plex Mono'" fontSize="11.5" fontWeight="600">
                    <tspan fill="#F59E0B">ED Stroke Surge</tspan>
                    <tspan fill="#64748B"> · </tspan>
                    <tspan fill="#2DD4BF">Auto-Balancing</tspan>
                  </text>
                </g>
              </g>
            </svg>
          </div>

        </div>

        {/* ================= 3. TWO WORKSPACES (PREVIEW SHOWCASE) ================= */}
        <section id="roles" className="mt-20 w-full scroll-mt-28 border-t border-[#3E4E5B]/60 pt-16">
          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="text-3xl font-extrabold text-[#F5F3ED] tracking-tight">
              Two workspaces, one synchronized schedule
            </h2>
            <p className="text-sm md:text-base text-[#BCC9D2] mt-2.5 leading-relaxed">
              Coordinators manage national coverage while neurologists accept verified emergency shifts in seconds.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">

            {/* Coordinator Workspace Card */}
            <div className="hover-lift bg-[#F1F0EC] text-[#101B2B] rounded-3xl border border-[#E4E3DF] p-5 sm:p-8 md:p-10 flex flex-col justify-between shadow-xl">
              <div>
                <div className="flex flex-wrap gap-3 items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#0D746D] bg-[#CCFBF1] px-3 py-1 rounded-full border border-teal-200/60">
                    Coordinator Workspace
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-800 font-semibold bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-200/50">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-pulse" />
                    LIVE DISPATCH
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-[#101B2B] mt-4 tracking-tight">Command Center</h3>
                <p className="text-sm text-[#475569] mt-2.5 leading-relaxed">
                  Real-time national grid oversight. Triage queue monitoring, predictive shortfall detection, and automated physician dispatch across 100+ partner hospitals.
                </p>

                <div className="mt-6 rounded-2xl bg-[#E8E6E0] border border-[#DCD9D0] p-4 space-y-2.5">
                  <div className="flex flex-wrap gap-3 items-center justify-between text-xs font-medium">
                    <span className="text-[#64748B] font-mono">Surge Mitigation Target</span>
                    <span className="text-[#0D746D] font-bold font-mono">&lt; 45s Response SLA</span>
                  </div>
                  <div className="w-full bg-[#D4D1C7] rounded-full h-2 overflow-hidden">
                    <div className="bg-[#0D9488] h-2 rounded-full w-[82%]" />
                  </div>
                  <div className="flex flex-wrap gap-3 items-center justify-between text-[11px] text-[#64748B] font-mono pt-1">
                    <span>Cross-regional pool balancing active</span>
                    <span className="text-emerald-700 font-bold">100+ Hospitals</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-[#E2DFD8] flex flex-wrap gap-3 items-center justify-between">
                <button
                  onClick={() => onGoToSignIn("coordinator")}
                  className="rounded-xl bg-[#101B2B] hover:bg-[#1E2E42] px-6 py-3.5 text-xs font-semibold text-[#F1F0EC] shadow-md transition flex items-center gap-2 group cursor-pointer"
                >
                  <span>Sign In to Command Center</span>
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
              </div>
            </div>

            {/* Physician Experience Card */}
            <div className="hover-lift bg-[#F1F0EC] text-[#101B2B] rounded-3xl border border-[#E4E3DF] p-5 sm:p-8 md:p-10 flex flex-col justify-between shadow-xl">
              <div>
                <div className="flex flex-wrap gap-3 items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#0D746D] bg-[#CCFBF1] px-3 py-1 rounded-full border border-teal-200/60">
                    Physician Experience
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-teal-800 font-semibold bg-teal-100 px-2.5 py-0.5 rounded-full border border-teal-200/50">
                    1-TAP HANDOFF
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-[#101B2B] mt-4 tracking-tight">Mobile & Web Handoff</h3>
                <p className="text-sm text-[#475569] mt-2.5 leading-relaxed">
                  Distraction-free emergency shift acceptance. Doctor rest intervals are checked against 8 clinical fatigue rules before alerts reach their phone. Zero patient PHI.
                </p>

                <div className="mt-6 rounded-2xl bg-[#E8E6E0] border border-[#DCD9D0] p-4 space-y-2.5">
                  <div className="flex flex-wrap gap-3 items-center justify-between text-xs font-medium">
                    <span className="text-[#1E293B] font-medium">Surge Shift Offer · Regional Match</span>
                    <span className="text-[#0D746D] font-bold font-mono text-[11px] bg-[#CCFBF1] px-2 py-0.5 rounded">60m Coverage</span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-[#475569] font-mono">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span>8 Rest Safeguards Passed · Medical License Active</span>
                  </div>
                  <div className="pt-1 flex flex-wrap gap-3 items-center justify-between text-[11px]">
                    <span className="text-[#64748B]">HIPAA Safe Harbor Compliance</span>
                    <span className="text-[#101B2B] font-bold font-mono">100% Verified</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-[#E2DFD8] flex flex-wrap gap-3 items-center justify-between">
                <button
                  onClick={() => onGoToSignIn("physician")}
                  className="rounded-xl bg-[#0D9488] hover:bg-[#0F766E] px-6 py-3.5 text-xs font-semibold text-white shadow-md transition flex items-center gap-2 group cursor-pointer"
                >
                  <span>Sign In as Physician</span>
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
              </div>
            </div>

          </div>
        </section>

        {/* ================= 4. REAL SEVARO CLINICAL PROOF (100% AUTHENTIC METRICS) ================= */}
        <section id="safety" className="mt-20 w-full border-t border-[#3E4E5B]/60 pt-16">
          <div className="text-center max-w-xl mx-auto mb-10">
            <h2 className="text-2xl md:text-3xl font-extrabold text-[#F5F3ED] tracking-tight">Clinical Performance Proof</h2>
            <p className="text-sm text-[#BCC9D2] mt-2">Published real-world outcomes delivered by Sevaro's tele-stroke network.</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            {/* Stat 1: < 45s */}
            <div className="bg-[#F1F0EC] text-[#101B2B] rounded-2xl border border-[#E4E3DF] p-5 text-center shadow-lg">
              <div className="text-3xl font-extrabold font-heading text-[#101B2B]">&lt; 45s</div>
              <div className="text-xs font-semibold text-[#1E293B] mt-1">Response Time SLA</div>
              <div className="text-[11px] text-[#64748B] mt-0.5">Powered by Synapse AI</div>
            </div>

            {/* Stat 2: 100+ Hospitals */}
            <div className="bg-[#F1F0EC] text-[#101B2B] rounded-2xl border border-[#E4E3DF] p-5 text-center shadow-lg">
              <div className="text-3xl font-extrabold font-heading text-[#0D9488]">100+</div>
              <div className="text-xs font-semibold text-[#1E293B] mt-1">Hospitals Served</div>
              <div className="text-[11px] text-[#64748B] mt-0.5">Across Emergency Depts</div>
            </div>

            {/* Stat 3: 30% Transfer Reduction */}
            <div className="bg-[#F1F0EC] text-[#101B2B] rounded-2xl border border-[#E4E3DF] p-5 text-center shadow-lg">
              <div className="text-3xl font-extrabold font-heading text-[#101B2B]">30%</div>
              <div className="text-xs font-semibold text-[#1E293B] mt-1">Transfer Reduction</div>
              <div className="text-[11px] text-[#64748B] mt-0.5">Avoiding Unnecessary Moves</div>
            </div>

            {/* Stat 4: 20% Reduced Length of Stay */}
            <div className="bg-[#F1F0EC] text-[#101B2B] rounded-2xl border border-[#E4E3DF] p-5 text-center shadow-lg">
              <div className="text-3xl font-extrabold font-heading text-emerald-700">20%</div>
              <div className="text-xs font-semibold text-[#1E293B] mt-1">Reduced Length of Stay</div>
              <div className="text-[11px] text-[#64748B] mt-0.5">Rapid Acute Intervention</div>
            </div>
          </div>
        </section>

      </main>
    </div>
  );
};
