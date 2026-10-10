// DTOs for Mobile-App-Contract.md v1.1. Class names match the contract's schema
// names; fields are camelCase. Every class has `parse(Object? json)` which is
// strict (see json.dart). Timestamps are UTC DateTime; format with time.dart.
import 'json.dart';

// ============================================================== enums

enum Role implements WireEnum {
  physician('physician'),
  clinicalLead('clinical_lead'),
  coordinator('coordinator'),
  admin('admin');

  const Role(this.wire);
  @override
  final String wire;
}

/// Physician-visible offer states (contract 4.2, 13.5).
enum OfferStatus implements WireEnum {
  sent('sent'),
  accepted('accepted'),
  declined('declined'),
  expired('expired'),
  withdrawn('withdrawn'),
  released('released');

  const OfferStatus(this.wire);
  @override
  final String wire;
}

enum StatusReason implements WireEnum {
  filledByAnotherPhysician('filled_by_another_physician'),
  gapClosed('gap_closed');

  const StatusReason(this.wire);
  @override
  final String wire;
}

enum OfferAction implements WireEnum {
  accept('accept'),
  decline('decline'),
  release('release');

  const OfferAction(this.wire);
  @override
  final String wire;
}

enum OfferOutcome implements WireEnum {
  accepted('accepted'),
  declined('declined'),
  alreadyFilled('already_filled'),
  expired('expired'),
  notOpen('not_open'),
  released('released');

  const OfferOutcome(this.wire);
  @override
  final String wire;
}

enum PreferencesOutcome implements WireEnum {
  updated('updated'),
  unchanged('unchanged'),
  openOfferExists('open_offer_exists');

  const PreferencesOutcome(this.wire);
  @override
  final String wire;
}

enum NotificationKind implements WireEnum {
  offer('offer'),
  reminder('reminder'),
  schedule('schedule'),
  outcome('outcome');

  const NotificationKind(this.wire);
  @override
  final String wire;
}

enum ConsultLevel implements WireEnum {
  critical('critical'),
  warning('warning'),
  ok('ok');

  const ConsultLevel(this.wire);
  @override
  final String wire;
}

enum DayKind implements WireEnum {
  day('day'),
  night('night'),
  off('off'),
  split('split');

  const DayKind(this.wire);
  @override
  final String wire;
}

enum TodayStatus implements WireEnum {
  onShift('on_shift'),
  offShift('off_shift');

  const TodayStatus(this.wire);
  @override
  final String wire;
}

enum ProposalStatus implements WireEnum {
  proposed('proposed'),
  approved('approved'),
  rejected('rejected'),
  cancelled('cancelled');

  const ProposalStatus(this.wire);
  @override
  final String wire;
}

enum ProposalOutcome implements WireEnum {
  approved('approved'),
  rejected('rejected'),
  alreadyDecided('already_decided');

  const ProposalOutcome(this.wire);
  @override
  final String wire;
}

enum CheckResult implements WireEnum {
  pass('pass'),
  fail('fail');

  const CheckResult(this.wire);
  @override
  final String wire;
}

enum BroadcastStatus implements WireEnum {
  open('open'),
  filled('filled'),
  unfilled('unfilled');

  const BroadcastStatus(this.wire);
  @override
  final String wire;
}

enum EscalationStatus implements WireEnum {
  pending('pending'),
  authorized('authorized');

  const EscalationStatus(this.wire);
  @override
  final String wire;
}

enum EscalationOutcome implements WireEnum {
  authorized('authorized'),
  alreadyAuthorized('already_authorized');

  const EscalationOutcome(this.wire);
  @override
  final String wire;
}

enum CoverageLevel implements WireEnum {
  short('short'),
  noOneFree('no_one_free'),
  atMinimum('at_minimum'),
  covered('covered');

  const CoverageLevel(this.wire);
  @override
  final String wire;
}

enum LeadShiftKind implements WireEnum {
  day('day'),
  night('night'),
  away('away'),
  offer('offer');

  const LeadShiftKind(this.wire);
  @override
  final String wire;
}

// ============================================================== shared

class Hospital {
  const Hospital({required this.hospitalId, required this.name});
  final String hospitalId;
  final String name;

  factory Hospital.fromJ(J j) => Hospital(hospitalId: j.str('hospital_id'), name: j.str('name'));
}

class TimeRange {
  const TimeRange({required this.start, required this.end});
  final DateTime start;
  final DateTime end;

  factory TimeRange.fromJ(J j) => TimeRange(start: j.time('start'), end: j.time('end'));
}

class PhysicianRef {
  const PhysicianRef({required this.physicianId, required this.displayName});
  final String physicianId;
  final String displayName;

  factory PhysicianRef.fromJ(J j) =>
      PhysicianRef(physicianId: j.str('physician_id'), displayName: j.str('display_name'));
}

class Staffing {
  const Staffing({required this.staffed, required this.required, this.marker});
  final int staffed;
  final int required;
  final String? marker;

  factory Staffing.fromJ(J j) => Staffing(
      staffed: j.integer('staffed'), required: j.integer('required'), marker: j.strN('marker'));
}

class TimedText {
  const TimedText({required this.at, required this.text});
  final DateTime at;
  final String text;

  factory TimedText.fromJ(J j) => TimedText(at: j.time('at'), text: j.str('text'));
}

// ============================================================== 4.1 Me

class Me {
  const Me({
    required this.userId,
    required this.role,
    required this.displayName,
    required this.physicianId,
    required this.permissions,
    required this.splitShiftOptIn,
    required this.offersReceived7d,
    required this.weeklyOfferLimit,
    required this.onShift,
    required this.shiftEnd,
    required this.serverNow,
  });

  final String userId;
  final Role role;
  final String displayName;
  final String? physicianId;
  final List<String> permissions;
  final bool? splitShiftOptIn;
  final int? offersReceived7d;
  final int? weeklyOfferLimit;
  final bool? onShift; // 13.2
  final DateTime? shiftEnd; // 13.2
  final DateTime serverNow;

  bool can(String permission) => permissions.contains(permission);

  factory Me.fromJ(J j) => Me(
        userId: j.str('user_id'),
        role: j.enumv('role', Role.values),
        displayName: j.str('display_name'),
        physicianId: j.strN('physician_id'),
        permissions: j.strings('permissions'),
        splitShiftOptIn: j.boolN('split_shift_opt_in'),
        offersReceived7d: j.intN('offers_received_7d'),
        weeklyOfferLimit: j.intN('weekly_offer_limit'),
        onShift: j.boolN('on_shift'),
        shiftEnd: j.timeN('shift_end'),
        serverNow: j.time('server_now'),
      );
  static Me parse(Object? json) => Me.fromJ(J(json, 'Me'));
}

class LoginResult {
  const LoginResult({required this.token, required this.me});
  final String token;
  final Me me;

  factory LoginResult.fromJ(J j) => LoginResult(token: j.str('token'), me: j.one('me', Me.fromJ));
  static LoginResult parse(Object? json) => LoginResult.fromJ(J(json, 'LoginResult'));
}

// ============================================================== 4.2 Offer

class NextStep {
  const NextStep({required this.at, required this.label});
  final DateTime at;
  final String label;

  factory NextStep.fromJ(J j) => NextStep(at: j.time('at'), label: j.str('label'));
}

class CoverageAfter {
  const CoverageAfter({required this.staffed, required this.required, required this.from});
  final int staffed;
  final int required;
  final DateTime from;

  factory CoverageAfter.fromJ(J j) => CoverageAfter(
      staffed: j.integer('staffed'), required: j.integer('required'), from: j.time('from'));
}

class Offer {
  const Offer({
    required this.offerId,
    required this.gapId,
    required this.hospitals,
    required this.start,
    required this.end,
    required this.hours,
    required this.reason,
    required this.status,
    required this.statusReason,
    required this.sentAt,
    required this.expiresAt,
    required this.respondedAt,
    required this.routingHospitals,
    required this.approvedAt,
    required this.gapSummary,
    required this.signInBy,
    required this.whyYou,
    required this.allowedActions,
    required this.nextSteps,
    required this.coverageAfter,
    required this.serverNow,
  });

  final String offerId;
  final String gapId;
  final List<Hospital> hospitals;
  final DateTime start;
  final DateTime end;
  final double hours;
  final String reason; // one-line fallback for whyYou
  final OfferStatus status;
  final StatusReason? statusReason;
  final DateTime sentAt;
  final DateTime expiresAt;
  final DateTime? respondedAt;
  final List<Hospital> routingHospitals;
  final DateTime approvedAt; // 13.5
  final String gapSummary; // 13.5
  final DateTime signInBy; // 13.5
  final List<String> whyYou; // 13.5
  final List<OfferAction> allowedActions; // 13.5 — show only these buttons
  final List<NextStep> nextSteps; // 13.5
  final CoverageAfter? coverageAfter; // 13.5

  /// Present on GET /offers/{id}; absent when embedded in another payload.
  final DateTime? serverNow;

  bool allows(OfferAction a) => allowedActions.contains(a);

  factory Offer.fromJ(J j) => Offer(
        offerId: j.str('offer_id'),
        gapId: j.str('gap_id'),
        hospitals: j.list('hospitals', Hospital.fromJ),
        start: j.time('start'),
        end: j.time('end'),
        hours: j.number('hours'),
        reason: j.str('reason'),
        status: j.enumv('status', OfferStatus.values),
        statusReason: j.enumN('status_reason', StatusReason.values),
        sentAt: j.time('sent_at'),
        expiresAt: j.time('expires_at'),
        respondedAt: j.timeN('responded_at'),
        routingHospitals: j.list('routing_hospitals', Hospital.fromJ),
        approvedAt: j.time('approved_at'),
        gapSummary: j.str('gap_summary'),
        signInBy: j.time('sign_in_by'),
        whyYou: j.strings('why_you'),
        allowedActions: j.enums('allowed_actions', OfferAction.values),
        nextSteps: j.list('next_steps', NextStep.fromJ),
        coverageAfter: j.oneN('coverage_after', CoverageAfter.fromJ),
        serverNow: j.timeN('server_now'),
      );
  static Offer parse(Object? json) => Offer.fromJ(J(json, 'Offer'));
}

class OfferList {
  const OfferList({required this.offers, required this.serverNow});
  final List<Offer> offers; // newest first
  final DateTime serverNow;

  bool get anySent => offers.any((o) => o.status == OfferStatus.sent);

  factory OfferList.fromJ(J j) =>
      OfferList(offers: j.list('offers', Offer.fromJ), serverNow: j.time('server_now'));
  static OfferList parse(Object? json) => OfferList.fromJ(J(json, 'OfferList'));
}

class OfferActionResult {
  const OfferActionResult(
      {required this.outcome, required this.applied, required this.offer, required this.serverNow});
  final OfferOutcome outcome; // the screen to show
  final bool applied;
  final Offer offer;
  final DateTime serverNow;

  factory OfferActionResult.fromJ(J j) => OfferActionResult(
        outcome: j.enumv('outcome', OfferOutcome.values),
        applied: j.boolean('applied'),
        offer: j.one('offer', Offer.fromJ),
        serverNow: j.time('server_now'),
      );
  static OfferActionResult parse(Object? json) => OfferActionResult.fromJ(J(json, 'OfferActionResult'));
}

// ============================================================== 4.6 Preferences

class PreferencesResult {
  const PreferencesResult({
    required this.applied,
    required this.outcome,
    required this.openOfferId,
    required this.me,
    required this.serverNow,
  });
  final bool applied;
  final PreferencesOutcome outcome;
  final String? openOfferId;
  final Me me;
  final DateTime serverNow;

  factory PreferencesResult.fromJ(J j) => PreferencesResult(
        applied: j.boolean('applied'),
        outcome: j.enumv('outcome', PreferencesOutcome.values),
        openOfferId: j.strN('open_offer_id'),
        me: j.one('me', Me.fromJ),
        serverNow: j.time('server_now'),
      );
  static PreferencesResult parse(Object? json) => PreferencesResult.fromJ(J(json, 'PreferencesResult'));
}

// ============================================================== 13.6 Notifications

class AppNotification {
  const AppNotification({
    required this.notificationId,
    required this.kind,
    required this.title,
    required this.body,
    required this.at,
    required this.offerId,
    required this.unread,
  });
  final String notificationId;
  final NotificationKind kind;
  final String title;
  final String body;
  final DateTime at;
  final String? offerId;
  final bool unread;

  factory AppNotification.fromJ(J j) => AppNotification(
        notificationId: j.str('notification_id'),
        kind: j.enumv('kind', NotificationKind.values),
        title: j.str('title'),
        body: j.str('body'),
        at: j.time('at'),
        offerId: j.strN('offer_id'),
        unread: j.boolean('unread'),
      );
}

class NotificationList {
  const NotificationList({required this.items, required this.serverNow});
  final List<AppNotification> items; // newest first
  final DateTime serverNow;

  int get unreadOffers => items.where((n) => n.unread && n.kind == NotificationKind.offer).length;

  factory NotificationList.fromJ(J j) => NotificationList(
      items: j.list('items', AppNotification.fromJ), serverNow: j.time('server_now'));
  static NotificationList parse(Object? json) => NotificationList.fromJ(J(json, 'NotificationList'));
}

// ============================================================== 13.3 MyShift

class ShiftConsult {
  const ShiftConsult({
    required this.consultId,
    required this.consultType,
    required this.hospitalName,
    required this.badge,
    required this.statusText,
    required this.level,
  });
  final String consultId;
  final String consultType;
  final String hospitalName;
  final String? badge;
  final String statusText;
  final ConsultLevel level;

  factory ShiftConsult.fromJ(J j) => ShiftConsult(
        consultId: j.str('consult_id'),
        consultType: j.str('consult_type'),
        hospitalName: j.str('hospital_name'),
        badge: j.strN('badge'),
        statusText: j.str('status_text'),
        level: j.enumv('level', ConsultLevel.values),
      );
}

class MyShift {
  const MyShift({
    required this.onShift,
    required this.shiftStart,
    required this.shiftEnd,
    required this.consultsToday,
    required this.callsToday,
    required this.hospitalsCount,
    required this.update,
    required this.consults,
    required this.nextShift,
    required this.serverNow,
  });
  final bool onShift;
  final DateTime? shiftStart;
  final DateTime? shiftEnd;
  final int consultsToday;
  final int callsToday;
  final int hospitalsCount;
  final TimedText? update;
  final List<ShiftConsult> consults;
  final TimeRange? nextShift;
  final DateTime serverNow;

  factory MyShift.fromJ(J j) => MyShift(
        onShift: j.boolean('on_shift'),
        shiftStart: j.timeN('shift_start'),
        shiftEnd: j.timeN('shift_end'),
        consultsToday: j.integer('consults_today'),
        callsToday: j.integer('calls_today'),
        hospitalsCount: j.integer('hospitals_count'),
        update: j.oneN('update', TimedText.fromJ),
        consults: j.list('consults', ShiftConsult.fromJ),
        nextShift: j.oneN('next_shift', TimeRange.fromJ),
        serverNow: j.time('server_now'),
      );
  static MyShift parse(Object? json) => MyShift.fromJ(J(json, 'MyShift'));
}

// ============================================================== 13.4 MySchedule

class ScheduleDay {
  const ScheduleDay({required this.date, required this.kind});
  final DateTime date; // UTC midnight of the calendar date
  final DayKind kind;

  factory ScheduleDay.fromJ(J j) =>
      ScheduleDay(date: j.date('date'), kind: j.enumv('kind', DayKind.values));
}

class TodaySummary {
  const TodaySummary({
    required this.status,
    required this.start,
    required this.end,
    required this.consults,
    required this.calls,
    required this.hospitals,
  });
  final TodayStatus status;
  final DateTime? start;
  final DateTime? end;
  final int consults;
  final int calls;
  final int hospitals;

  factory TodaySummary.fromJ(J j) => TodaySummary(
        status: j.enumv('status', TodayStatus.values),
        start: j.timeN('start'),
        end: j.timeN('end'),
        consults: j.integer('consults'),
        calls: j.integer('calls'),
        hospitals: j.integer('hospitals'),
      );
}

class WithYouRow {
  const WithYouRow({
    required this.displayName,
    required this.label,
    required this.start,
    required this.end,
    required this.isYou,
  });
  final String displayName;
  final String label;
  final DateTime start;
  final DateTime end;
  final bool isYou;

  factory WithYouRow.fromJ(J j) => WithYouRow(
        displayName: j.str('display_name'),
        label: j.str('label'),
        start: j.time('start'),
        end: j.time('end'),
        isYou: j.boolean('is_you'),
      );
}

class WithYou {
  const WithYou({
    required this.hospitalName,
    required this.windowStart,
    required this.windowEnd,
    required this.rows,
    required this.note,
  });
  final String hospitalName;
  final DateTime windowStart;
  final DateTime windowEnd;
  final List<WithYouRow> rows;
  final String? note;

  factory WithYou.fromJ(J j) => WithYou(
        hospitalName: j.str('hospital_name'),
        windowStart: j.time('window_start'),
        windowEnd: j.time('window_end'),
        rows: j.list('rows', WithYouRow.fromJ),
        note: j.strN('note'),
      );
}

class MySchedule {
  const MySchedule({
    required this.weekStart,
    required this.days,
    required this.today,
    required this.withYou,
    required this.nextShift,
    required this.serverNow,
  });
  final DateTime weekStart; // UTC midnight of the Sunday
  final List<ScheduleDay> days; // seven, Sunday first
  final TodaySummary today;
  final WithYou? withYou;
  final TimeRange? nextShift; // null → "Not in this roster yet"
  final DateTime serverNow;

  factory MySchedule.fromJ(J j) => MySchedule(
        weekStart: j.date('week_start'),
        days: j.list('days', ScheduleDay.fromJ),
        today: j.one('today', TodaySummary.fromJ),
        withYou: j.oneN('with_you', WithYou.fromJ),
        nextShift: j.oneN('next_shift', TimeRange.fromJ),
        serverNow: j.time('server_now'),
      );
  static MySchedule parse(Object? json) => MySchedule.fromJ(J(json, 'MySchedule'));
}

// ============================================================== 5.2 LeadQueue

class ProposalSummary {
  const ProposalSummary({
    required this.proposalId,
    required this.gapId,
    required this.hospitals,
    required this.start,
    required this.end,
    required this.recipientCount,
    required this.proposedAt,
  });
  final String proposalId;
  final String gapId;
  final List<Hospital> hospitals;
  final DateTime start;
  final DateTime end;
  final int recipientCount;
  final DateTime proposedAt;

  factory ProposalSummary.fromJ(J j) => ProposalSummary(
        proposalId: j.str('proposal_id'),
        gapId: j.str('gap_id'),
        hospitals: j.list('hospitals', Hospital.fromJ),
        start: j.time('start'),
        end: j.time('end'),
        recipientCount: j.integer('recipient_count'),
        proposedAt: j.time('proposed_at'),
      );
}

class Escalation {
  const Escalation({
    required this.escalationId,
    required this.hospitalName,
    required this.reason,
    required this.proposedIntervention,
    required this.status,
    required this.createdAt,
    required this.authorizedBy,
    required this.authorizedAt,
  });
  final String escalationId;
  final String hospitalName;
  final String reason;
  final String proposedIntervention;
  final EscalationStatus status;
  final DateTime createdAt;
  final String? authorizedBy;
  final DateTime? authorizedAt;

  factory Escalation.fromJ(J j) => Escalation(
        escalationId: j.str('escalation_id'),
        hospitalName: j.str('hospital_name'),
        reason: j.str('reason'),
        proposedIntervention: j.str('proposed_intervention'),
        status: j.enumv('status', EscalationStatus.values),
        createdAt: j.time('created_at'),
        authorizedBy: j.strN('authorized_by'),
        authorizedAt: j.timeN('authorized_at'),
      );
  static Escalation parse(Object? json) => Escalation.fromJ(J(json, 'Escalation'));
}

class LeadQueue {
  const LeadQueue({
    required this.pendingCount,
    required this.proposals,
    required this.escalations,
    required this.automatedActions,
    required this.serverNow,
  });
  final int pendingCount;
  final List<ProposalSummary> proposals; // newest first
  final List<Escalation> escalations; // newest first
  final List<TimedText> automatedActions; // 13.7 "Done automatically"
  final DateTime serverNow;

  factory LeadQueue.fromJ(J j) => LeadQueue(
        pendingCount: j.integer('pending_count'),
        proposals: j.list('proposals', ProposalSummary.fromJ),
        escalations: j.list('escalations', Escalation.fromJ),
        automatedActions: j.list('automated_actions', TimedText.fromJ),
        serverNow: j.time('server_now'),
      );
  static LeadQueue parse(Object? json) => LeadQueue.fromJ(J(json, 'LeadQueue'));
}

// ============================================================== 5.3 Proposal

class Gap {
  const Gap({
    required this.hospitals,
    required this.start,
    required this.end,
    required this.hours,
    required this.required,
    required this.counted,
    required this.shortfall,
  });
  final List<Hospital> hospitals;
  final DateTime start;
  final DateTime end;
  final double hours;
  final int required;
  final int counted;
  final int shortfall;

  factory Gap.fromJ(J j) => Gap(
        hospitals: j.list('hospitals', Hospital.fromJ),
        start: j.time('start'),
        end: j.time('end'),
        hours: j.number('hours'),
        required: j.integer('required'),
        counted: j.integer('counted'),
        shortfall: j.integer('shortfall'),
      );
}

class Recipient {
  const Recipient(
      {required this.physicianId, required this.displayName, required this.rank, required this.rankReason});
  final String physicianId;
  final String displayName;
  final int rank;
  final String rankReason;

  factory Recipient.fromJ(J j) => Recipient(
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        rank: j.integer('rank'),
        rankReason: j.str('rank_reason'),
      );
}

/// Used for `Proposal.excluded` and `ProposalActionResult.skipped`.
class ExcludedPhysician {
  const ExcludedPhysician(
      {required this.physicianId, required this.displayName, required this.failedRule, required this.detail});
  final String physicianId;
  final String displayName;
  final String failedRule; // "R1".."R8"
  final String detail;

  factory ExcludedPhysician.fromJ(J j) => ExcludedPhysician(
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        failedRule: j.str('failed_rule'),
        detail: j.str('detail'),
      );
}

class TrapCheckSummary {
  const TrapCheckSummary({required this.result, required this.explanation});
  final CheckResult result;
  final String explanation;

  factory TrapCheckSummary.fromJ(J j) => TrapCheckSummary(
      result: j.enumv('result', CheckResult.values), explanation: j.str('explanation'));
}

class CoveragePreview {
  const CoveragePreview({required this.times, required this.without, required this.withOffer});
  final List<DateTime> times;
  final List<Staffing> without;
  final List<Staffing> withOffer; // JSON key "with"

  factory CoveragePreview.fromJ(J j) => CoveragePreview(
        times: j.times('times'),
        without: j.list('without', Staffing.fromJ),
        withOffer: j.list('with', Staffing.fromJ),
      );
}

class Proposal {
  const Proposal({
    required this.proposalId,
    required this.gapId,
    required this.gap,
    required this.recipients,
    required this.excluded,
    required this.trapCheck,
    required this.coveragePreview,
    required this.status,
    required this.proposedBy,
    required this.proposedAt,
    required this.decidedBy,
    required this.decidedAt,
    required this.rejectReason,
    required this.serverNow,
  });
  final String proposalId;
  final String gapId;
  final Gap gap;
  final List<Recipient> recipients;
  final List<ExcludedPhysician> excluded;
  final TrapCheckSummary trapCheck;
  final CoveragePreview coveragePreview; // 13.7
  final ProposalStatus status;
  final String proposedBy;
  final DateTime proposedAt;
  final String? decidedBy;
  final DateTime? decidedAt;
  final String? rejectReason;
  final DateTime? serverNow; // absent when embedded

  factory Proposal.fromJ(J j) => Proposal(
        proposalId: j.str('proposal_id'),
        gapId: j.str('gap_id'),
        gap: j.one('gap', Gap.fromJ),
        recipients: j.list('recipients', Recipient.fromJ),
        excluded: j.list('excluded', ExcludedPhysician.fromJ),
        trapCheck: j.one('trap_check', TrapCheckSummary.fromJ),
        coveragePreview: j.one('coverage_preview', CoveragePreview.fromJ),
        status: j.enumv('status', ProposalStatus.values),
        proposedBy: j.str('proposed_by'),
        proposedAt: j.time('proposed_at'),
        decidedBy: j.strN('decided_by'),
        decidedAt: j.timeN('decided_at'),
        rejectReason: j.strN('reject_reason'),
        serverNow: j.timeN('server_now'),
      );
  static Proposal parse(Object? json) => Proposal.fromJ(J(json, 'Proposal'));
}

class SentOffer {
  const SentOffer({required this.offerId, required this.physicianId, required this.status});
  final String offerId;
  final String physicianId;
  final OfferStatus status;

  factory SentOffer.fromJ(J j) => SentOffer(
      offerId: j.str('offer_id'),
      physicianId: j.str('physician_id'),
      status: j.enumv('status', OfferStatus.values));
}

class ProposalActionResult {
  const ProposalActionResult({
    required this.outcome,
    required this.applied,
    required this.proposal,
    required this.offers,
    required this.skipped,
    required this.serverNow,
  });
  final ProposalOutcome outcome;
  final bool applied;
  final Proposal proposal;
  final List<SentOffer> offers;
  final List<ExcludedPhysician> skipped;
  final DateTime serverNow;

  factory ProposalActionResult.fromJ(J j) => ProposalActionResult(
        outcome: j.enumv('outcome', ProposalOutcome.values),
        applied: j.boolean('applied'),
        proposal: j.one('proposal', Proposal.fromJ),
        offers: j.list('offers', SentOffer.fromJ),
        skipped: j.list('skipped', ExcludedPhysician.fromJ),
        serverNow: j.time('server_now'),
      );
  static ProposalActionResult parse(Object? json) =>
      ProposalActionResult.fromJ(J(json, 'ProposalActionResult'));
}

// ============================================================== 5.5 – 5.6

class RuleResult {
  const RuleResult({required this.rule, required this.name, required this.passed, required this.detail});
  final String rule;
  final String name;
  final bool passed;
  final String detail;

  factory RuleResult.fromJ(J j) => RuleResult(
      rule: j.str('rule'), name: j.str('name'), passed: j.boolean('passed'), detail: j.str('detail'));
}

class Candidate {
  const Candidate({
    required this.physicianId,
    required this.displayName,
    required this.eligible,
    required this.rank,
    required this.rules,
  });
  final String physicianId;
  final String displayName;
  final bool eligible;
  final int? rank;
  final List<RuleResult> rules; // R1..R8 in order

  RuleResult? get firstFailed => rules.where((r) => !r.passed).firstOrNull;

  factory Candidate.fromJ(J j) => Candidate(
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        eligible: j.boolean('eligible'),
        rank: j.intN('rank'),
        rules: j.list('rules', RuleResult.fromJ),
      );
}

class CandidateList {
  const CandidateList(
      {required this.gapId, required this.evaluatedAt, required this.candidates, required this.serverNow});
  final String gapId;
  final DateTime evaluatedAt;
  final List<Candidate> candidates;
  final DateTime serverNow;

  factory CandidateList.fromJ(J j) => CandidateList(
        gapId: j.str('gap_id'),
        evaluatedAt: j.time('evaluated_at'),
        candidates: j.list('candidates', Candidate.fromJ),
        serverNow: j.time('server_now'),
      );
  static CandidateList parse(Object? json) => CandidateList.fromJ(J(json, 'CandidateList'));
}

class TrapCheck {
  const TrapCheck({
    required this.gapId,
    required this.result,
    required this.explanation,
    required this.seedConsults,
    required this.joinerProjectedConsults,
    required this.busiestPeerProjectedConsults,
    required this.serverNow,
  });
  final String gapId;
  final CheckResult result;
  final String explanation;
  final int seedConsults;
  final int joinerProjectedConsults;
  final int busiestPeerProjectedConsults;
  final DateTime serverNow;

  factory TrapCheck.fromJ(J j) => TrapCheck(
        gapId: j.str('gap_id'),
        result: j.enumv('result', CheckResult.values),
        explanation: j.str('explanation'),
        seedConsults: j.integer('seed_consults'),
        joinerProjectedConsults: j.integer('joiner_projected_consults'),
        busiestPeerProjectedConsults: j.integer('busiest_peer_projected_consults'),
        serverNow: j.time('server_now'),
      );
  static TrapCheck parse(Object? json) => TrapCheck.fromJ(J(json, 'TrapCheck'));
}

// ============================================================== 5.7 BroadcastList

class BroadcastOffer {
  const BroadcastOffer({
    required this.offerId,
    required this.physicianId,
    required this.displayName,
    required this.status,
    required this.statusReason,
    required this.expiresAt,
    required this.respondedAt,
  });
  final String offerId;
  final String physicianId;
  final String displayName;
  final OfferStatus status;
  final StatusReason? statusReason;
  final DateTime expiresAt;
  final DateTime? respondedAt;

  factory BroadcastOffer.fromJ(J j) => BroadcastOffer(
        offerId: j.str('offer_id'),
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        status: j.enumv('status', OfferStatus.values),
        statusReason: j.enumN('status_reason', StatusReason.values),
        expiresAt: j.time('expires_at'),
        respondedAt: j.timeN('responded_at'),
      );
}

class Broadcast {
  const Broadcast({
    required this.proposalId,
    required this.gapId,
    required this.hospitals,
    required this.start,
    required this.end,
    required this.status,
    required this.filledBy,
    required this.offers,
  });
  final String proposalId;
  final String gapId;
  final List<Hospital> hospitals;
  final DateTime start;
  final DateTime end;
  final BroadcastStatus status;
  final PhysicianRef? filledBy;
  final List<BroadcastOffer> offers;

  factory Broadcast.fromJ(J j) => Broadcast(
        proposalId: j.str('proposal_id'),
        gapId: j.str('gap_id'),
        hospitals: j.list('hospitals', Hospital.fromJ),
        start: j.time('start'),
        end: j.time('end'),
        status: j.enumv('status', BroadcastStatus.values),
        filledBy: j.oneN('filled_by', PhysicianRef.fromJ),
        offers: j.list('offers', BroadcastOffer.fromJ),
      );
}

class BroadcastList {
  const BroadcastList({required this.broadcasts, required this.serverNow});
  final List<Broadcast> broadcasts;
  final DateTime serverNow;

  factory BroadcastList.fromJ(J j) =>
      BroadcastList(broadcasts: j.list('broadcasts', Broadcast.fromJ), serverNow: j.time('server_now'));
  static BroadcastList parse(Object? json) => BroadcastList.fromJ(J(json, 'BroadcastList'));
}

/// Emitted by LeadFeed.answers when a recipient's offer changes status between
/// two polls. Not a wire schema.
class AnswerEvent {
  const AnswerEvent({required this.broadcast, required this.offer, required this.previousStatus});
  final Broadcast broadcast;
  final BroadcastOffer offer;
  final OfferStatus previousStatus;

  OfferStatus get status => offer.status;
}

// ============================================================== 5.8 Escalation result

class EscalationActionResult {
  const EscalationActionResult(
      {required this.outcome, required this.applied, required this.escalation, required this.serverNow});
  final EscalationOutcome outcome;
  final bool applied;
  final Escalation escalation;
  final DateTime serverNow;

  factory EscalationActionResult.fromJ(J j) => EscalationActionResult(
        outcome: j.enumv('outcome', EscalationOutcome.values),
        applied: j.boolean('applied'),
        escalation: j.one('escalation', Escalation.fromJ),
        serverNow: j.time('server_now'),
      );
  static EscalationActionResult parse(Object? json) =>
      EscalationActionResult.fromJ(J(json, 'EscalationActionResult'));
}

// ============================================================== 5.10 AuditLog

class AuditEntry {
  const AuditEntry({required this.at, required this.actor, required this.action, required this.detail});
  final DateTime at;
  final String actor;
  final String action; // free text; don't branch on it
  final String detail;

  factory AuditEntry.fromJ(J j) => AuditEntry(
      at: j.time('at'), actor: j.str('actor'), action: j.str('action'), detail: j.str('detail'));
}

class AuditLog {
  const AuditLog({required this.gapId, required this.entries, required this.serverNow});
  final String gapId;
  final List<AuditEntry> entries; // oldest first
  final DateTime serverNow;

  factory AuditLog.fromJ(J j) => AuditLog(
      gapId: j.str('gap_id'), entries: j.list('entries', AuditEntry.fromJ), serverNow: j.time('server_now'));
  static AuditLog parse(Object? json) => AuditLog.fromJ(J(json, 'AuditLog'));
}

// ============================================================== 13.8 CoverageBoard

class CoverageColumn {
  const CoverageColumn({required this.label, required this.at});
  final String label;
  final DateTime at;

  factory CoverageColumn.fromJ(J j) => CoverageColumn(label: j.str('label'), at: j.time('at'));
}

class CoverageRow {
  const CoverageRow({
    required this.hospitalId,
    required this.name,
    required this.statusText,
    required this.level,
    required this.cells,
  });
  final String hospitalId;
  final String name;
  final String statusText;
  final CoverageLevel level;
  final List<Staffing> cells;

  factory CoverageRow.fromJ(J j) => CoverageRow(
        hospitalId: j.str('hospital_id'),
        name: j.str('name'),
        statusText: j.str('status_text'),
        level: j.enumv('level', CoverageLevel.values),
        cells: j.list('cells', Staffing.fromJ),
      );
}

class Footnote {
  const Footnote({required this.marker, required this.text});
  final String marker;
  final String text;

  factory Footnote.fromJ(J j) => Footnote(marker: j.str('marker'), text: j.str('text'));
}

class CoverageBoard {
  const CoverageBoard(
      {required this.columns, required this.hospitals, required this.footnotes, required this.serverNow});
  final List<CoverageColumn> columns;
  final List<CoverageRow> hospitals; // server's order
  final List<Footnote> footnotes;
  final DateTime serverNow;

  factory CoverageBoard.fromJ(J j) => CoverageBoard(
        columns: j.list('columns', CoverageColumn.fromJ),
        hospitals: j.list('hospitals', CoverageRow.fromJ),
        footnotes: j.list('footnotes', Footnote.fromJ),
        serverNow: j.time('server_now'),
      );
  static CoverageBoard parse(Object? json) => CoverageBoard.fromJ(J(json, 'CoverageBoard'));
}

// ============================================================== 13.9 LeadSchedule

class ScheduleBanner {
  const ScheduleBanner({required this.text, required this.proposalId});
  final String text;
  final String proposalId;

  factory ScheduleBanner.fromJ(J j) => ScheduleBanner(text: j.str('text'), proposalId: j.str('proposal_id'));
}

class LeadShift {
  const LeadShift({
    required this.physicianId,
    required this.displayName,
    required this.kind,
    required this.start,
    required this.end,
  });
  final String physicianId;
  final String displayName;
  final LeadShiftKind kind;
  final DateTime? start; // required for on_shift rows, nullable for off_shift
  final DateTime? end;

  factory LeadShift.onShift(J j) => LeadShift(
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        kind: j.enumv('kind', LeadShiftKind.values),
        start: j.time('start'),
        end: j.time('end'),
      );
  factory LeadShift.offShift(J j) => LeadShift(
        physicianId: j.str('physician_id'),
        displayName: j.str('display_name'),
        kind: j.enumv('kind', LeadShiftKind.values),
        start: j.timeN('start'),
        end: j.timeN('end'),
      );
}

class LeadSchedule {
  const LeadSchedule({
    required this.date,
    required this.banner,
    required this.windowStart,
    required this.windowEnd,
    required this.onShift,
    required this.offShift,
    required this.offShiftWorkingToday,
    required this.offShiftTotal,
    required this.serverNow,
  });
  final DateTime date; // UTC midnight of the calendar date
  final ScheduleBanner? banner;
  final DateTime windowStart;
  final DateTime windowEnd;
  final List<LeadShift> onShift;
  final List<LeadShift> offShift;
  final int offShiftWorkingToday;
  final int offShiftTotal;
  final DateTime serverNow;

  factory LeadSchedule.fromJ(J j) => LeadSchedule(
        date: j.date('date'),
        banner: j.oneN('banner', ScheduleBanner.fromJ),
        windowStart: j.time('window_start'),
        windowEnd: j.time('window_end'),
        onShift: j.list('on_shift', LeadShift.onShift),
        offShift: j.list('off_shift', LeadShift.offShift),
        offShiftWorkingToday: j.integer('off_shift_working_today'),
        offShiftTotal: j.integer('off_shift_total'),
        serverNow: j.time('server_now'),
      );
  static LeadSchedule parse(Object? json) => LeadSchedule.fromJ(J(json, 'LeadSchedule'));
}

// ============================================================== 6 Error body

class ApiErrorBody {
  const ApiErrorBody({required this.code, required this.message});
  final String code;
  final String message;

  factory ApiErrorBody.fromJ(J j) {
    final e = j.obj('error');
    return ApiErrorBody(code: e.str('code'), message: e.str('message'));
  }
  static ApiErrorBody parse(Object? json) => ApiErrorBody.fromJ(J(json, 'Error'));
}
