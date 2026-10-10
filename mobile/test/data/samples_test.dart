import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fake_samples.g.dart';

// Contract section 10: every sample parses with its schema; every bad/ file
// fails; offer/notification/action payloads carry no patient data.

final parsers = <String, Object Function(Object?)>{
  'mobile_me_physician.json': Me.parse,
  'mobile_me_lead.json': Me.parse,
  'mobile_me_shah.json': Me.parse,
  'mobile_me_brennan.json': Me.parse,
  'mobile_offers.json': OfferList.parse,
  'mobile_offer_accept_accepted.json': OfferActionResult.parse,
  'mobile_offer_accept_already_filled.json': OfferActionResult.parse,
  'mobile_offer_accept_expired.json': OfferActionResult.parse,
  'mobile_offer_decline_declined.json': OfferActionResult.parse,
  'mobile_offer_release_released.json': OfferActionResult.parse,
  'mobile_preferences_updated.json': PreferencesResult.parse,
  'mobile_preferences_open_offer.json': PreferencesResult.parse,
  'mobile_lead_queue.json': LeadQueue.parse,
  'mobile_proposal.json': Proposal.parse,
  'mobile_proposal_approved.json': ProposalActionResult.parse,
  'mobile_proposal_already_decided.json': ProposalActionResult.parse,
  'mobile_candidates.json': CandidateList.parse,
  'mobile_trap_check.json': TrapCheck.parse,
  'mobile_lead_offers.json': BroadcastList.parse,
  'mobile_audit.json': AuditLog.parse,
  'mobile_escalation.json': Escalation.parse,
  'mobile_login.json': LoginResult.parse,
  'mobile_notifications.json': NotificationList.parse,
  'mobile_shift_on.json': MyShift.parse,
  'mobile_shift_off.json': MyShift.parse,
  'mobile_schedule.json': MySchedule.parse,
  'mobile_lead_coverage.json': CoverageBoard.parse,
  'mobile_lead_schedule.json': LeadSchedule.parse,
  'mobile_error_401.json': ApiErrorBody.parse,
  'mobile_error_403.json': ApiErrorBody.parse,
};

/// `bad/<schema>__<what>.json` → parser for `<schema>`.
final badParsers = <String, Object Function(Object?)>{
  'me': Me.parse,
  'offer': Offer.parse,
  'offer_list': OfferList.parse,
  'offer_action_result': OfferActionResult.parse,
};

const contracts = 'assets/contracts'; // flutter test runs from mobile/

void main() {
  test('every sample in assets/contracts has a parser and parses', () {
    final onDisk = Directory(contracts)
        .listSync()
        .whereType<File>()
        .map((f) => f.uri.pathSegments.last)
        .where((n) => n.endsWith('.json'))
        .toSet();
    expect(onDisk, parsers.keys.toSet(), reason: 'add new samples to the parsers map');
    for (final e in parsers.entries) {
      final json = jsonDecode(File('$contracts/${e.key}').readAsStringSync());
      expect(() => e.value(json), returnsNormally, reason: e.key);
    }
  });

  test('embedded fake samples match assets/contracts (re-run tool/gen_samples.py)', () {
    for (final e in kSamples.entries) {
      final disk = jsonDecode(File('$contracts/${e.key}').readAsStringSync());
      expect(jsonDecode(e.value), disk, reason: e.key);
    }
  });

  test('every bad/ file fails with ParseError', () {
    final files = Directory('$contracts/bad').listSync().whereType<File>().toList();
    expect(files, isNotEmpty);
    for (final f in files) {
      final name = f.uri.pathSegments.last;
      final schema = name.split('__').first;
      final parse = badParsers[schema];
      expect(parse, isNotNull, reason: 'no parser for $name');
      expect(() => parse!(jsonDecode(f.readAsStringSync())), throwsA(isA<ParseError>()), reason: name);
    }
  });

  test('mobile_offers.json has one offer in each physician-visible state', () {
    final list = OfferList.parse(jsonDecode(kSamples['mobile_offers.json']!));
    final seen = {for (final o in list.offers) (o.status, o.statusReason)};
    expect(seen, containsAll({
      (OfferStatus.sent, null),
      (OfferStatus.accepted, null),
      (OfferStatus.declined, null),
      (OfferStatus.expired, null),
      (OfferStatus.withdrawn, StatusReason.filledByAnotherPhysician),
      (OfferStatus.withdrawn, StatusReason.gapClosed),
      (OfferStatus.released, null),
    }));
  });

  test('no patient data in offer, notification and action-result samples', () {
    const banned = {'consult_id', 'consult_type', 'patient', 'patient_id', 'mrn', 'dob', 'age', 'symptoms'};
    final files = kSamples.keys.where((n) =>
        n.startsWith('mobile_offer') || n.startsWith('mobile_notifications') || n.startsWith('mobile_preferences'));
    expect(files, isNotEmpty);
    for (final name in files) {
      final keys = <String>{};
      void walk(Object? v) {
        if (v is Map) {
          keys.addAll(v.keys.cast<String>());
          v.values.forEach(walk);
        } else if (v is List) {
          v.forEach(walk);
        }
      }

      final json = jsonDecode(kSamples[name]!);
      walk(json);
      expect(keys.intersection(banned), isEmpty, reason: name);
      expect(kSamples[name]!.contains(RegExp(r'CON-\d+')), isFalse, reason: '$name mentions a consult');
    }
  });

  test('timestamps keep their instant and become UTC', () {
    final me = Me.parse(jsonDecode(kSamples['mobile_me_physician.json']!));
    expect(me.serverNow.isUtc, isTrue);
    expect(me.serverNow, DateTime.utc(2026, 3, 17, 22, 20));
    expect(formatEt(me.serverNow), '18:20');
  });
}
