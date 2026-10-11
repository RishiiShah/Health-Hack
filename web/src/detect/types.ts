// Display shapes for the detect screens, filled from the server snapshot by fromSnapshot.ts.
export type QueueItem = {
  id: string; label: string; kind: string; level: string; rank: number; reason: string;
  where: string; why: string; fix: string; fixKind: string; fixReason: string; alternatives: string[]; approver: string; physicianId: string | null;
};
export type Consult = {
  id: string; hospital: string; type: string; stage: string; minutesInStage: number; minutesSinceReceived: number;
  physicianId: string | null; physicianName: string | null; routingFailures: number;
  level: string; limit: string; warningMinutes: number | null; criticalMinutes: number | null;
  standardAge: number | null; standardClock: string;
};
export type Physician = {
  id: string; name: string; status: string; derived: string; camera: string; helper: string;
  canTakeCalls: boolean; workload: string; reason: string; flags: string[];
  calls: number | null; consults: number | null; openConsults: number | null; pendingNotes: number;
  minutesToShiftEnd: number | null; hospitals: { id: string; name: string }[];
};
export type Headline = {
  openConsults: number; pastCritical: number; freePhysicians: number; totalPhysicians: number;
  signalDisagreements: number; shortIn90: number; waitingOnPerson: number;
};
export type DetectSnapshot = { headline: Headline; queue: QueueItem[]; consults: Consult[]; physicians: Physician[] };
