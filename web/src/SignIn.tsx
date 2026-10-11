import React, { useState, useEffect } from "react";

type Role = "coordinator" | "lead" | "physician";

interface SignInProps {
  initialRole?: Role;
  onSignIn: (role: Role) => void;
  onBackToLanding: () => void;
}

export const SignIn: React.FC<SignInProps> = ({ initialRole = "coordinator", onSignIn, onBackToLanding }) => {
  const [selectedRole, setSelectedRole] = useState<Role>(initialRole);
  const [email, setEmail] = useState(
    initialRole === "physician"
      ? "shah@demo.sevaro"
      : initialRole === "lead"
      ? "lead@demo.sevaro"
      : "coord@demo.sevaro"
  );
  const [password, setPassword] = useState("••••••••••••");

  useEffect(() => {
    setSelectedRole(initialRole);
    setEmail(
      initialRole === "physician"
        ? "shah@demo.sevaro"
        : initialRole === "lead"
        ? "lead@demo.sevaro"
        : "coord@demo.sevaro"
    );
  }, [initialRole]);

  const selectRole = (role: Role) => {
    setSelectedRole(role);
    setEmail(role === "coordinator" ? "coord@demo.sevaro" : role === "lead" ? "lead@demo.sevaro" : "shah@demo.sevaro");
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSignIn(selectedRole);
  };

  const roleTitle = selectedRole === "coordinator" ? "Coordinator" : selectedRole === "lead" ? "Clinical Lead" : "Physician";

  return (
    <div className="min-h-screen bg-[#F7F4EB] text-slate-900 flex flex-col p-6">
      {/* Top Header */}
      <div className="max-w-4xl mx-auto w-full flex items-center justify-between pb-6">
        <button onClick={onBackToLanding} className="flex items-center gap-2 text-slate-900 hover:text-slate-700 transition">
          <span className="relative block h-5 w-6">
            <i className="absolute left-0 top-0 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-teal-600" />
            <i className="absolute left-2.5 top-1.5 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-[#161E2E]" />
          </span>
          <strong className="text-base font-bold tracking-tight text-slate-900">overlap</strong>
        </button>
        <button onClick={onBackToLanding} className="text-xs font-medium text-slate-500 hover:text-slate-800 transition">
          ← Back to Overview
        </button>
      </div>

      {/* Comfortably Centered Sign-In Box */}
      <div className="flex-1 flex items-center justify-center -mt-8 py-6">
        <div className="max-w-md w-full bg-white/95 rounded-3xl p-8 border border-[#E5E0D5] shadow-xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold font-heading text-slate-900">Sign in</h1>
          <p className="text-xs text-slate-500 mt-1">Select your operating role to access your dashboard</p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-2">I work as</label>
          <div className="grid grid-cols-3 gap-2">
            {([
              ["coordinator", "Coordinator", "Watch network & dispatch"],
              ["lead", "Clinical lead", "Approve offers & escalations"],
              ["physician", "Physician", "Your shifts & consults"],
            ] as const).map(([role, title, description]) => (
              <button
                type="button"
                key={role}
                onClick={() => selectRole(role)}
                className={`p-3 rounded-2xl text-left border transition-all ${
                  selectedRole === role
                    ? "border-teal-600 bg-teal-50/60 ring-2 ring-teal-600/20"
                    : "border-slate-200 bg-slate-50/50 hover:bg-slate-50"
                }`}
              >
                <div className="text-xs font-bold text-slate-900">{title}</div>
                <div className="text-[10px] text-slate-500 mt-1 leading-snug">{description}</div>
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Work email</label>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full text-xs p-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono"
            />
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-medium text-slate-700">Password</label>
              <span className="text-[11px] text-teal-700 cursor-pointer">Forgot it?</span>
            </div>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full text-xs p-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono"
            />
          </div>
          <button
            type="submit"
            className="w-full py-3.5 bg-teal-700 hover:bg-teal-800 text-white rounded-xl font-bold text-xs shadow-md transition-all hover:scale-[1.01]"
          >
            Sign in as {roleTitle}
          </button>
        </form>

        <div className="pt-4 border-t border-slate-100 text-center">
          <div className="text-[11px] text-slate-500 mb-2 font-medium">Or 1-click launch into demo account:</div>
          <div className="flex flex-col gap-1.5 text-xs font-mono">
            {([
              ["coordinator", "coord@demo.sevaro", "Coordinator"],
              ["lead", "lead@demo.sevaro", "Lead"],
              ["physician", "shah@demo.sevaro", "Physician"],
            ] as const).map(([role, address, label]) => (
              <button
                key={role}
                onClick={() => onSignIn(role)}
                className="py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-left flex justify-between"
              >
                <span>{address}</span>
                <span className="text-teal-700 font-sans font-semibold">Launch {label} →</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  </div>
  );
};
