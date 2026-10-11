import 'package:flutter/material.dart';

import '../shared.dart';
import '../schedule_timeline.dart';
import 'preview_offer.dart';
import 'preview_widgets.dart';

class PreviewApprovals extends StatefulWidget {
  const PreviewApprovals({super.key});
  @override
  State<PreviewApprovals> createState() => _PreviewApprovalsState();
}

class _PreviewApprovalsState extends State<PreviewApprovals> {
  final _reason = TextEditingController();
  bool _rejecting = false;
  bool _busy = false;
  String? _decision;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _decide(bool approve) async {
    if (_busy ||
        _decision != null ||
        (!approve && _reason.text.trim().isEmpty)) {
      return;
    }
    setState(() => _busy = true);
    final confirmed = await confirmAction(
      context,
      title: approve ? 'Approve and send?' : 'Reject this proposal?',
      message: approve
          ? 'Send the sample offer to Dr. Okafor.'
          : _reason.text.trim(),
      confirmLabel: approve ? 'Approve and send' : 'Confirm rejection',
    );
    if (!mounted) return;
    if (!confirmed) {
      setState(() => _busy = false);
      return;
    }
    await Future<void>.delayed(const Duration(milliseconds: 650));
    if (!mounted) return;
    setState(() {
      _decision = approve ? 'approved' : 'rejected';
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      PreviewHeading(
        _decision == null ? '1 waiting for you' : 'All caught up',
        caption: 'Tue 17 Mar · 18:22 ET',
      ),
      PreviewCard(
        accent: previewTeal,
        children: [
          PreviewPill(
            _decision == null
                ? 'Waiting for you · gap at 19:00 ET'
                : _decision == 'approved'
                ? 'Approved · sample offer sent'
                : 'Rejected',
          ),
          const SizedBox(height: 16),
          const Text(
            'Dr. Okafor for Suncrest',
            style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text('19:00 to 23:00 ET · off shift'),
          const SizedBox(height: 24),
          Table(
            defaultVerticalAlignment: TableCellVerticalAlignment.middle,
            children: [
              TableRow(
                children: [
                  for (final text in ['', '19:00', '19:15', '19:30'])
                    Padding(
                      padding: const EdgeInsets.all(4),
                      child: Text(
                        text,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                ],
              ),
              for (final row in [
                ('Without', '1/2', const Color(0xFFF8E2DC)),
                ('With her', '2/2', const Color(0xFFDDEEE4)),
              ])
                TableRow(
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(4),
                      child: Text(row.$1),
                    ),
                    for (var i = 0; i < 3; i++)
                      Container(
                        margin: const EdgeInsets.all(3),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: row.$3,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(row.$2, textAlign: TextAlign.center),
                      ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 8),
          const ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('Checked 6 off-shift physicians'),
            children: [
              ListTile(
                leading: Icon(Icons.check_circle_outline, color: previewGreen),
                title: Text('Okafor passes all rules'),
              ),
              ListTile(
                title: Text('Alvarez'),
                subtitle: Text('Not credentialed at Suncrest'),
              ),
              ListTile(
                title: Text('Cho'),
                subtitle: Text('Already scheduled at 19:00 ET'),
              ),
              ListTile(
                title: Text('Haddad, Brennan'),
                subtitle: Text('Not opted in to extra shifts'),
              ),
              ListTile(
                title: Text('Menon'),
                subtitle: Text('63 h this week; limit 60'),
              ),
            ],
          ),
          const ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('Trap check · passed'),
            children: [
              Padding(
                padding: EdgeInsets.only(bottom: 16),
                child: Text(
                  'Joiner limited to Suncrest and seeded at 12 consults; gap closes, no other hospital worsens.',
                ),
              ),
            ],
          ),
          if (_decision == null) ...[
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _busy ? null : () => _decide(true),
              child: const Text('Approve and send to Dr. Okafor'),
            ),
            const SizedBox(height: 10),
            if (_rejecting) ...[
              TextField(
                controller: _reason,
                enabled: !_busy,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'Reason for rejection',
                ),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 10),
            ],
            OutlinedButton(
              onPressed: _busy || (_rejecting && _reason.text.trim().isEmpty)
                  ? null
                  : () {
                      if (_rejecting) {
                        _decide(false);
                      } else {
                        setState(() => _rejecting = true);
                      }
                    },
              child: Text(_rejecting ? 'Reject proposal' : 'Reject'),
            ),
            if (_busy)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Center(
                  child: CircularProgressIndicator(
                    semanticsLabel: 'Sending decision',
                  ),
                ),
              ),
          ] else ...[
            const SizedBox(height: 16),
            Notice(
              _decision == 'approved'
                  ? 'Sample offer sent to Dr. Okafor.'
                  : 'Proposal rejected: ${_reason.text.trim()}',
            ),
            if (_decision == 'approved')
              TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const PreviewSurface(child: PreviewOffer()),
                  ),
                ),
                child: const Text('Open physician offer preview'),
              ),
            TextButton(
              onPressed: () => setState(() {
                _decision = null;
                _rejecting = false;
                _reason.clear();
              }),
              child: const Text('Reset sample proposal'),
            ),
          ],
        ],
      ),
      const PreviewHeading('Done automatically'),
      const PreviewCard(
        children: [
          Text('18:19 ET · Re-routed CON-2105 at Oak Valley'),
          Divider(height: 24),
          Text('18:12 ET · Flagged CON-2110, owner unavailable'),
        ],
      ),
    ],
  );
}

class PreviewCoverage extends StatelessWidget {
  const PreviewCoverage({super.key});

  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      const PreviewHeading(
        'Coverage across your team',
        caption: 'Staffed / required · training data',
      ),
      const PreviewPill('Tue 17 Mar · 18:22 ET'),
      const SizedBox(height: 20),
      for (final row in const [
        (
          'Suncrest',
          'Short at 19:00 · offer out',
          '3/2',
          '1/2*',
          '1/1',
          Color(0xFFB53C2C),
        ),
        (
          'Oak Valley',
          'No one free right now',
          '1/1',
          '1/1',
          '1/1',
          Color(0xFF93600B),
        ),
        ('Redwood Univ.', 'At minimum', '2/2', '2/2', '2/2', Color(0xFF93600B)),
        (
          'Cedar Ridge',
          'At minimum from 19:00',
          '4/2',
          '2/2',
          '2/2',
          Color(0xFF93600B),
        ),
        (
          'Northfield',
          'No one free right now',
          '4/2',
          '3/2',
          '3/2',
          Color(0xFF93600B),
        ),
        (
          'Meadowlands',
          'No one free right now',
          '4/1',
          '2/1',
          '2/1',
          Color(0xFF93600B),
        ),
        (
          'Harbor Regional',
          'No one free right now',
          '4/1',
          '3/1',
          '3/1',
          Color(0xFF93600B),
        ),
        (
          'Westbridge',
          'No one free right now',
          '4/1',
          '2/1',
          '2/1',
          Color(0xFF93600B),
        ),
        (
          'Bluewater',
          'No one free right now',
          '2/1',
          '2/1',
          '2/1',
          Color(0xFF93600B),
        ),
        ('Lakeview', 'Covered', '4/1', '2/1', '2/1', previewGreen),
        ('Highland Valley', 'Covered', '3/1', '2/1', '2/1', previewGreen),
        ('Silver Oak', 'Covered', '2/1', '2/1', '2/1', previewGreen),
      ])
        PreviewCard(
          children: [
            Text(
              row.$1,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            Text(row.$2, style: TextStyle(color: row.$6)),
            const SizedBox(height: 16),
            Wrap(
              spacing: 16,
              runSpacing: 12,
              children: [
                for (final cell in [
                  ('Now', row.$3),
                  ('19:00 ET', row.$4),
                  ('19:45 ET', row.$5),
                ])
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(cell.$1, style: const TextStyle(fontSize: 12)),
                      const SizedBox(height: 6),
                      PreviewPill(cell.$2, color: row.$6),
                    ],
                  ),
              ],
            ),
          ],
        ),
      const Text(
        '* Counts Dr. Cho, who is scheduled from 19:00 ET but not signed in yet.',
      ),
    ],
  );
}

class PreviewLeadSchedule extends StatefulWidget {
  const PreviewLeadSchedule({super.key, required this.onReview});
  final VoidCallback onReview;
  @override
  State<PreviewLeadSchedule> createState() => _PreviewLeadScheduleState();
}

class _PreviewLeadScheduleState extends State<PreviewLeadSchedule> {
  int _day = 17;
  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      PreviewWeek(
        selectedDay: _day,
        onSelected: (day) => setState(() => _day = day),
      ),
      if (_day != 17)
        const Notice(
          'No sample roster for this day. Select 17 March to inspect the design.',
        )
      else ...[
        PreviewCard(
          color: previewInk,
          children: [
            const Text(
              'Suncrest short at 19:00 ET. Offer waiting.',
              style: TextStyle(color: Colors.white),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: widget.onReview,
              child: const Text('Review proposal'),
            ),
          ],
        ),
        const PreviewCard(
          children: [
            PreviewHeading(
              'On shift · 8',
              caption: '12:00 to 24:00 ET · snapshot at 18:22 ET',
            ),
            ScheduleTimeline(
              startHour: 12,
              endHour: 24,
              currentHour: 18 + 22 / 60,
              currentTimeLabel: '18:22',
              tickEvery: 3,
              entries: [
                TimelineEntry(
                  name: 'Patel',
                  hoursLabel: '12:00?20:00 ET',
                  startHour: 12,
                  endHour: 20,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Kim',
                  hoursLabel: '12:00?20:00 ET',
                  startHour: 12,
                  endHour: 20,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Ramirez',
                  hoursLabel: '12:00?19:00 ET',
                  startHour: 12,
                  endHour: 19,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Brooks',
                  hoursLabel: '12:00?21:00 ET',
                  startHour: 12,
                  endHour: 21,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Shah',
                  hoursLabel: '12:00?20:00 ET',
                  startHour: 12,
                  endHour: 20,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Lee',
                  hoursLabel: '12:00?19:00 ET',
                  startHour: 12,
                  endHour: 19,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Torres',
                  hoursLabel: '12:00?22:00 ET',
                  startHour: 12,
                  endHour: 22,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Williams',
                  hoursLabel: 'away until 20:00 ET',
                  startHour: 12,
                  endHour: 20,
                  kind: TimelineKind.away,
                ),
              ],
            ),
            Divider(height: 32),
            PreviewHeading('Off shift ? 3 of 6 working today'),
            ScheduleTimeline(
              startHour: 12,
              endHour: 24,
              currentHour: 18 + 22 / 60,
              currentTimeLabel: '18:22',
              tickEvery: 3,
              entries: [
                TimelineEntry(
                  name: 'Okafor',
                  hoursLabel: 'offer ? 19:00?23:00 ET',
                  startHour: 19,
                  endHour: 23,
                  kind: TimelineKind.offer,
                ),
                TimelineEntry(
                  name: 'Cho',
                  hoursLabel: 'night ? from 19:00 ET',
                  startHour: 19,
                  endHour: 24,
                  kind: TimelineKind.night,
                ),
                TimelineEntry(
                  name: 'Haddad',
                  hoursLabel: 'night ? from 20:00 ET',
                  startHour: 20,
                  endHour: 24,
                  kind: TimelineKind.night,
                ),
              ],
            ),
          ],
        ),
      ],
    ],
  );
}
