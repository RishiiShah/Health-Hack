// Display shapes for the detect screens, filled from the server snapshot by fromSnapshot.ts.
export type QueueItem = {
  id: string; label: string; kind: string; level: string; rank: number; reason: string; watchOnly: boolean;
  where: string; why: string; fix: string; fixKind: string; fixReason: string; alternatives: string[]; approver: string; physicianId: string | null;
};
export type Consult = { id: string; hospital: string; type: string; stage: string; minutesInStage: number; minutesSinceReceived: number; level: string; limit: string };
export type Physician = { id: string; name: string; status: string; derived: string; camera: string; helper: string; canTakeCalls: boolean; workload: string; reason: string };
export type Headline = {
  openConsults: number; pastCritical: number; freePhysicians: number; totalPhysicians: number;
  signalDisagreements: number; shortIn90: number; waitingOnPerson: number;
  overloadedPhysicians: number; forecastHorizonMinutes: number;
};
export type DetectSnapshot = { headline: Headline; queue: QueueItem[]; consults: Consult[]; physicians: Physician[] };
