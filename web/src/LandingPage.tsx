import React from "react";

type Role = "coordinator" | "lead" | "physician";

interface LandingPageProps {
  onEnter: (role: Role) => void;
  onGoToSignIn: (role?: Role) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onGoToSignIn }) => {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen bg-[#E8E6E0] text-slate-900 overflow-x-hidden selection:bg-[#E2ECF3] selection:text-[#101B2B] flex flex-col justify-between">
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
          box-shadow: 0 20px 35px -8px rgba(15, 23, 42, 0.08), 0 8px 16px -4px rgba(15, 23, 42, 0.03);
          border-color: rgba(13, 148, 136, 0.35);
        }
      `}</style>

      {/* ================= 1. FLOATING CENTERED NAVBAR ================= */}
      <nav className="fixed top-5 inset-x-0 mx-auto z-50 flex w-[calc(100%-48px)] items-center justify-between rounded-full border border-slate-200/90 bg-white/90 px-6 py-3 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.05)]">
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} className="flex items-center gap-2">
          <span className="relative block h-5 w-6">
            <i className="absolute left-0 top-0 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-[#B8D8EB]" />
            <i className="absolute left-2.5 top-1.5 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-[#101B2B]" />
          </span>
          <strong className="text-base font-bold tracking-tight text-slate-900">overlap</strong>
        </button>

        <div className="hidden md:flex items-center gap-1 bg-slate-100/80 p-1 rounded-full border border-slate-200/50 text-xs font-semibold text-slate-600">
          <button onClick={() => scrollTo("overview")} className="bg-white text-slate-900 px-4 py-1.5 rounded-full shadow-sm">Overview</button>
          <button onClick={() => scrollTo("network")} className="px-3.5 py-1.5 hover:text-slate-900 transition">Network</button>
          <button onClick={() => scrollTo("roles")} className="px-3.5 py-1.5 hover:text-slate-900 transition">Workspaces</button>
          <button onClick={() => scrollTo("safety")} className="px-3.5 py-1.5 hover:text-slate-900 transition">Prototype Scope</button>
        </div>

        <button
          onClick={() => onGoToSignIn("coordinator")}
          className="text-xs font-semibold text-slate-900 hover:text-[#101B2B] transition px-3 py-1.5"
        >
          Sign In →
        </button>
      </nav>

      {/* ================= 2. MAIN HERO SECTION ================= */}
      <main id="overview" className="relative w-full mx-auto px-4 sm:px-6 pt-32 pb-16 flex-1 flex flex-col items-center">

        {/* CENTERED HEADLINE */}
        <section className="text-center max-w-3xl mx-auto mb-8 px-4">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold font-heading text-slate-900 tracking-tight leading-[1.08]">
            Spot coverage gaps,<br />
            <span className="font-normal italic font-serif text-[#101B2B]">before</span> shifts change.
          </h1>
          <p className="mt-4 text-base md:text-lg text-slate-600 max-w-xl mx-auto leading-relaxed">
            Deterministic coverage planning, ranked alerts, and lead-approved physician offers using the Sevaro challenge kit.
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button
              onClick={() => onGoToSignIn("coordinator")}
              className="rounded-full bg-[#B8D8EB] px-7 py-3.5 text-xs font-semibold text-[#101B2B] shadow-lg shadow-[#101B2B]/10 transition hover:-translate-y-0.5 hover:bg-[#A6CAE0]"
            >
              Sign In to Command Center →
            </button>
            <button
              onClick={() => onGoToSignIn("physician")}
              className="rounded-full border border-slate-300 bg-white px-6 py-3.5 text-xs font-medium text-slate-700 transition hover:-translate-y-0.5 hover:border-slate-400 shadow-sm"
            >
              Sign In as Physician
            </button>
          </div>
        </section>

        {/* ================= THE LIVING TOPOGRAPHIC US NETWORK MAP (ALWAYS IN MOTION) ================= */}
        <div id="network" className="relative w-full h-[420px] md:h-[min(64vh,720px)] md:min-h-[460px] flex items-center justify-center my-4">

          {/* Implemented forecast horizon, not a response-time promise. */}
          <div className="anim-float-1 absolute top-4 left-2 md:top-8 md:left-6 z-20 rounded-2xl bg-white/95 backdrop-blur-xl border border-slate-200/90 px-5 py-4 shadow-[0_16px_40px_-10px_rgba(15,23,42,0.08)]">
            <div className="text-[11px] font-mono text-slate-500 font-medium">Coverage forecast</div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl md:text-4xl font-extrabold text-slate-900 font-heading whitespace-nowrap">90+</span>
              <span className="text-xs text-slate-500 font-medium whitespace-nowrap">minutes ahead</span>
            </div>
          </div>

          {/* Fixed official reference kit size. */}
          <div className="anim-float-2 absolute bottom-6 right-2 md:bottom-12 md:right-8 z-20 rounded-2xl bg-white/95 backdrop-blur-xl border border-slate-200/90 p-4 md:p-5 flex items-center gap-3.5 shadow-[0_16px_40px_-10px_rgba(15,23,42,0.08)]">
            <span className="text-3xl md:text-4xl font-extrabold text-slate-900 font-heading">12</span>
            <div className="text-xs font-semibold text-slate-700 leading-snug">
              Hospitals in the<br />Official Reference Kit
            </div>
          </div>

          {/* BASE HIGH-RESOLUTION TOPOGRAPHIC TERRAIN RELIEF MAP */}
          <div className="relative w-full h-full flex items-center justify-center">
            <img
              src="/us_network_map.jpg"
              alt="Illustrative US network map; not the official hospital locations"
              className="w-full h-full object-contain pointer-events-none select-none"
            />

            {/* LIVING MOTION SVG OVERLAY: CONTINUOUSLY STREAMING COMETS & PULSES */}
            <svg viewBox="0 0 1376 768" className="absolute inset-0 w-full h-full pointer-events-auto" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="cyanBeam" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#14B8A6" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#2DD4BF" stopOpacity="1" />
                  <stop offset="100%" stopColor="#B8D8EB" stopOpacity="0.9" />
                </linearGradient>

                <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* ROUTING ARCS */}
              <path d="M 340 195 Q 500 330 695 545" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.65" />
              <path d="M 288 392 Q 420 340 565 395" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.65" />
              <path d="M 565 395 Q 640 450 695 545" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.65" />
              <path d="M 695 545 Q 770 430 838 355" fill="none" stroke="url(#cyanBeam)" strokeWidth="3" opacity="0.75" />
              <path d="M 838 355 Q 950 310 1050 345" fill="none" stroke="url(#cyanBeam)" strokeWidth="3" opacity="0.75" />
              <path d="M 695 545 Q 890 470 1050 345" fill="none" stroke="url(#cyanBeam)" strokeWidth="2.5" opacity="0.6" />

              {/* GLOWING CYAN COMETS (CONTINUOUS MOTION ACROSS THE MAP) */}
              <circle r="6" fill="#B8D8EB" filter="url(#glow)">
                <animateMotion dur="2.8s" repeatCount="indefinite" path="M 340 195 Q 500 330 695 545" />
              </circle>
              <circle r="5" fill="#B8D8EB" filter="url(#glow)">
                <animateMotion dur="2.4s" repeatCount="indefinite" path="M 288 392 Q 420 340 565 395" />
              </circle>
              <circle r="5.5" fill="#B8D8EB" filter="url(#glow)">
                <animateMotion dur="2.2s" repeatCount="indefinite" path="M 695 545 Q 770 430 838 355" />
              </circle>
              <circle r="6" fill="#B8D8EB" filter="url(#glow)">
                <animateMotion dur="2.5s" repeatCount="indefinite" path="M 838 355 Q 950 310 1050 345" />
              </circle>
              <circle r="5" fill="#B8D8EB" filter="url(#glow)">
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
                <circle cx="0" cy="0" r="6" fill="#B8D8EB" stroke="#FFFFFF" strokeWidth="2" />
                <text x="18" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#101B2B">Seattle</text>
              </g>

              <g transform="translate(288, 392)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="0.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="0.5s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#B8D8EB" stroke="#FFFFFF" strokeWidth="2" />
                <text x="18" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#101B2B">San Francisco</text>
              </g>

              <g transform="translate(565, 395)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="1s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="1s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#B8D8EB" stroke="#FFFFFF" strokeWidth="2" />
                <text x="0" y="24" textAnchor="middle" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#101B2B">Denver</text>
              </g>

              <g transform="translate(838, 355)">
                <circle cx="0" cy="0" r="14" fill="rgba(20, 184, 166, 0.25)">
                  <animate attributeName="r" values="8;16;8" dur="3s" begin="1.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="1.5s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="6" fill="#B8D8EB" stroke="#FFFFFF" strokeWidth="2" />
                <text x="0" y="24" textAnchor="middle" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#101B2B">Chicago</text>
              </g>

              <g transform="translate(1050, 345)">
                <circle cx="0" cy="0" r="16" fill="rgba(20, 184, 166, 0.3)">
                  <animate attributeName="r" values="8;18;8" dur="3s" begin="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" begin="2s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="7" fill="#B8D8EB" stroke="#FFFFFF" strokeWidth="2" />
                <text x="20" y="5" fontFamily="'IBM Plex Sans'" fontSize="16" fontWeight="700" fill="#101B2B">New York</text>
              </g>

              {/* DALLAS HUB & FIXED 280px CAPSULE PILL */}
              <g transform="translate(695, 545)" className="cursor-pointer">
                <circle cx="0" cy="0" r="9" fill="#D97706" stroke="#FFFFFF" strokeWidth="2.5" />
                <text x="20" y="6" fontFamily="'IBM Plex Sans'" fontSize="17" fontWeight="800" fill="#B45309">Dallas</text>

                <g transform="translate(0, -42)">
                  <rect x="-140" y="-15" width="280" height="30" rx="15" fill="#101B2B" stroke="#334155" strokeWidth="1.2" />
                  <polygon points="-6,15 0,21 6,15" fill="#101B2B" />
                  <text x="0" y="5" textAnchor="middle" fontFamily="'IBM Plex Mono'" fontSize="11.5" fontWeight="600">
                    <tspan fill="#F59E0B">ED Stroke Surge</tspan>
                    <tspan fill="#64748B"> · </tspan>
                    <tspan fill="#2DD4BF">Coverage review</tspan>
                  </text>
                </g>
              </g>
            </svg>
          </div>

        </div>

        <p className="text-center text-xs text-slate-600">Illustrative network map; locations and animation are not live hospital data.</p>

        {/* ================= 3. TWO WORKSPACES (PREVIEW SHOWCASE) ================= */}
        <section id="roles" className="mt-20 w-full scroll-mt-28 border-t border-slate-200/80 pt-16">

          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">
              One workflow, three operating roles
            </h2>
            <p className="text-sm md:text-base text-slate-600 mt-2.5 leading-relaxed">
              Coordinators review coverage gaps, clinical leads approve offers, and physicians reply in their own workspace.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">

            {/* Coordinator Workspace Card */}
            <div className="hover-lift bg-white rounded-3xl border border-[#E2DFD8] p-5 sm:p-8 md:p-10 flex flex-col justify-between shadow-sm">
              <div>
                <div className="flex flex-wrap gap-3 items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#101B2B] bg-[#E2ECF3] px-3 py-1 rounded-full border border-[#B8D8EB]/60">
                    Coordinator Workspace
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-600 font-semibold bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200/50">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    COVERAGE PLANNING
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-slate-900 mt-4 tracking-tight">Command Center</h3>
                <p className="text-sm text-slate-600 mt-2.5 leading-relaxed">
                  Review the live consult queue, projected coverage shortfalls, and each candidate's eligibility before proposing an offer for lead approval.
                </p>

                <div className="mt-6 rounded-2xl bg-slate-50 border border-slate-200/70 p-4 space-y-2.5">
                  <div className="flex flex-wrap gap-3 items-center justify-between text-xs font-medium">
                    <span className="text-slate-500 font-mono">Decision policy</span>
                    <span className="text-[#101B2B] font-bold font-mono">Severity first</span>
                  </div>
                  <div className="flex flex-wrap gap-3 items-center justify-between text-[11px] text-slate-400 font-mono pt-1">
                    <span>Deterministic replay and explanations</span>
                    <span className="text-emerald-600 font-bold">12 kit hospitals</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-slate-100 flex flex-wrap gap-3 items-center justify-between">
                <button
                  onClick={() => onGoToSignIn("coordinator")}
                  className="rounded-xl bg-[#101B2B] hover:bg-slate-900 px-6 py-3.5 text-xs font-semibold text-white shadow-md transition flex items-center gap-2 group"
                >
                  <span>Sign In to Command Center</span>
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
                <span className="text-xs font-mono text-slate-400">Desktop Web Optimized</span>
              </div>
            </div>

            {/* Physician Experience Card */}
            <div className="hover-lift bg-white rounded-3xl border border-[#E2DFD8] p-5 sm:p-8 md:p-10 flex flex-col justify-between shadow-sm">
              <div>
                <div className="flex flex-wrap gap-3 items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#101B2B] bg-[#E2ECF3] px-3 py-1 rounded-full border border-[#B8D8EB]/60">
                    Physician Experience
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-[#101B2B] font-semibold bg-[#E2ECF3] px-2.5 py-0.5 rounded-full border border-[#B8D8EB]/50">
                    1-TAP HANDOFF
                  </span>
                </div>

                <h3 className="text-2xl font-bold text-slate-900 mt-4 tracking-tight">Mobile & Web Handoff</h3>
                <p className="text-sm text-slate-600 mt-2.5 leading-relaxed">
                  Review and reply to approved shift offers. Eligibility checks use the supplied credentials, availability, rest, hours, and offer limits. Acceptance awaits observed arrival before routing.
                </p>

                <div className="mt-6 rounded-2xl bg-[#101B2B]/5 border border-[#101B2B]/15 p-4 space-y-2.5">
                  <div className="flex flex-wrap gap-3 items-center justify-between text-xs font-medium">
                    <span className="text-slate-700 font-medium">Shift offer workflow</span>
                    <span className="text-[#101B2B] font-bold font-mono text-[11px] bg-[#E2ECF3]/70 px-2 py-0.5 rounded">Lead approved</span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-600 font-mono">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span>Eligibility results and decline reasons</span>
                  </div>
                  <div className="pt-1 flex flex-wrap gap-3 items-center justify-between text-[11px]">
                    <span className="text-slate-500">Routing begins</span>
                    <span className="text-slate-900 font-bold font-mono">On observed arrival</span>
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-slate-100 flex flex-wrap gap-3 items-center justify-between">
                <button
                  onClick={() => onGoToSignIn("physician")}
                  className="rounded-xl bg-[#B8D8EB] hover:bg-[#A6CAE0] px-6 py-3.5 text-xs font-semibold text-[#101B2B] shadow-md transition flex items-center gap-2 group"
                >
                  <span>Sign In as Physician</span>
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
                <span className="text-xs font-mono text-slate-400">Mobile Responsive</span>
              </div>
            </div>

          </div>
        </section>

        {/* Verified implementation scope; no clinical outcome claims. */}
        <section id="safety" className="mt-20 w-full border-t border-slate-200/80 pt-16">
          <div className="text-center max-w-xl mx-auto mb-10">
            <h2 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">Challenge Prototype Scope</h2>
            <p className="text-sm text-slate-600 mt-2">Replays the supplied challenge data and supports reviewed staffing decisions. Clinical outcomes and production compliance have not been validated.</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            {/* Supplied baseline coverage. */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 text-center shadow-sm">
              <div className="text-2xl font-extrabold font-heading text-slate-900">24 hours</div>
              <div className="text-xs font-semibold text-slate-800 mt-1">Weekday Baselines</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Weekend data not supplied</div>
            </div>

            {/* Fixed reference hospitals. */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 text-center shadow-sm">
              <div className="text-2xl font-extrabold font-heading text-[#101B2B]">12</div>
              <div className="text-xs font-semibold text-slate-800 mt-1">Reference Hospitals</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Official Sevaro kit</div>
            </div>

            {/* Fixed reference physicians. */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 text-center shadow-sm">
              <div className="text-2xl font-extrabold font-heading text-slate-900">14</div>
              <div className="text-xs font-semibold text-slate-800 mt-1">Reference Physicians</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Supplied roster and credentials</div>
            </div>

            {/* Observed arrivals gate routing. */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-5 text-center shadow-sm">
              <div className="text-2xl font-extrabold font-heading text-emerald-600">3 roles</div>
              <div className="text-xs font-semibold text-slate-800 mt-1">Reviewed Offer Loop</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Coordinator · Lead · Physician</div>
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200/80 pt-8 pb-12 text-center text-xs text-slate-400 font-mono">
        © 2026 Overlap Systems · Sevaro Tele-Stroke Challenge · Decision Support Prototype
      </footer>
    </div>
  );
};
