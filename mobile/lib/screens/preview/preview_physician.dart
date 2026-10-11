import 'package:flutter/material.dart';

import '../shared.dart';
import '../schedule_timeline.dart';
import 'preview_offer.dart';
import 'preview_widgets.dart';

class PreviewShift extends StatelessWidget {
  const PreviewShift({super.key, this.onShift = true, required this.onOffers});
  final bool onShift;
  final VoidCallback onOffers;

  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      PreviewHeading(
        onShift ? 'Your shift, at a glance' : "You're off shift",
        caption: onShift
            ? 'Dr. Priya Shah · until 20:00 ET'
            : 'Dr. Grace Okafor · off shift',
      ),
      if (!onShift) ...[
        const PreviewCard(
          children: [
            Icon(Icons.nights_stay_outlined, size: 40, color: previewTeal),
            SizedBox(height: 16),
            Text(
              'Take a moment to recharge.',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            SizedBox(height: 8),
            Text(
              'Check Offers for coverage requests approved by your clinical lead.',
            ),
          ],
        ),
        FilledButton(onPressed: onOffers, child: const Text('View offers')),
      ] else ...[
        const PreviewCard(
          color: Color(0xFFE4EFEB),
          children: [
            PreviewPill('Schedule updated · 18:24 ET'),
            SizedBox(height: 12),
            Text(
              'CON-2114, a stroke consult from Suncrest, was assigned to you.',
            ),
          ],
        ),
        for (final consult in const [
          (
            'CON-2114',
            'New · Stroke',
            'Suncrest Medical Pavilion',
            'Contact the hospital within 3 min',
            Color(0xFFB4372A),
          ),
          (
            'CON-2104',
            'Stroke',
            'Meadowlands Community',
            'On the phone now · 10 min in stage',
            previewTeal,
          ),
          (
            'CON-2113',
            'Note due',
            'Suncrest Medical Pavilion',
            'Note open 12 of 30 min',
            Color(0xFF855700),
          ),
        ])
          PreviewCard(
            accent: consult.$5,
            children: [
              PreviewPill(consult.$2, color: consult.$5),
              const SizedBox(height: 12),
              Text(
                consult.$1,
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(consult.$3),
              const SizedBox(height: 16),
              Text(
                consult.$4,
                style: TextStyle(
                  color: consult.$5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        const Wrap(
          spacing: 16,
          runSpacing: 8,
          children: [
            PreviewPill('1 h 36 min left'),
            PreviewPill('15 consults today'),
          ],
        ),
      ],
    ],
  );
}

class PreviewOffers extends StatelessWidget {
  const PreviewOffers({super.key, required this.optedIn});
  final bool optedIn;

  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      const PreviewHeading(
        'A little extra coverage.\nA big difference.',
        caption: 'Dr. Grace Okafor · off shift',
      ),
      const PreviewPill('2 of 3 requests this week'),
      const SizedBox(height: 20),
      if (!optedIn) ...[
        const Notice("You won't receive coverage requests."),
        const SizedBox(height: 16),
      ],
      for (final item in [
        if (optedIn) ('New request', 'Suncrest Medical Pavilion', 'sent'),
        ("You're on", 'Suncrest Medical Pavilion', 'accepted'),
        ('Missed', 'Suncrest Medical Pavilion', 'expired'),
      ])
        PreviewCard(
          children: [
            PreviewPill(
              item.$1,
              color: item.$3 == 'expired' ? previewOrange : previewTeal,
            ),
            const SizedBox(height: 16),
            Text(
              item.$2,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text('19:00 to 23:00 ET · 4 hours'),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => PreviewSurface(
                    child: PreviewOffer(initialScenario: item.$3),
                  ),
                ),
              ),
              child: Text('View ${item.$1.toLowerCase()}'),
            ),
          ],
        ),
    ],
  );
}

class PreviewPhysicianSchedule extends StatefulWidget {
  const PreviewPhysicianSchedule({super.key});
  @override
  State<PreviewPhysicianSchedule> createState() =>
      _PreviewPhysicianScheduleState();
}

class _PreviewPhysicianScheduleState extends State<PreviewPhysicianSchedule> {
  int _day = 17;
  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      PreviewWeek(
        selectedDay: _day,
        onSelected: (day) => setState(() => _day = day),
      ),
      if (_day != 17)
        PreviewCard(
          children: [
            Text('$_day March', style: const TextStyle(fontSize: 22)),
            const SizedBox(height: 12),
            const Text(
              'No sample roster for this day. Select 17 March to inspect the design.',
            ),
          ],
        )
      else ...[
        const PreviewCard(
          children: [
            PreviewHeading('Today', caption: 'Tuesday 17 March'),
            PreviewPill('On shift'),
            SizedBox(height: 16),
            Text(
              '08:00 to 20:00 ET',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
            ),
            SizedBox(height: 12),
            Text('1 h 38 min left'),
            SizedBox(height: 12),
            Wrap(
              spacing: 16,
              runSpacing: 8,
              children: [
                Text('15 consults'),
                Text('18 calls'),
                Text('5 hospitals'),
              ],
            ),
          ],
        ),
        const PreviewCard(
          children: [
            PreviewHeading('With you at Suncrest'),
            ScheduleTimeline(
              startHour: 6,
              endHour: 24,
              currentHour: 18 + 22 / 60,
              currentTimeLabel: '18:22',
              tickEvery: 3,
              entries: [
                TimelineEntry(
                  name: 'Ramirez',
                  hoursLabel: '07:00?19:00 ET',
                  startHour: 7,
                  endHour: 19,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Lee',
                  hoursLabel: '08:00?19:00 ET',
                  startHour: 8,
                  endHour: 19,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'You',
                  hoursLabel: '08:00?20:00 ET',
                  startHour: 8,
                  endHour: 20,
                  kind: TimelineKind.day,
                ),
                TimelineEntry(
                  name: 'Cho',
                  hoursLabel: '19:00?24:00 ET',
                  startHour: 19,
                  endHour: 24,
                  kind: TimelineKind.night,
                ),
              ],
            ),
            SizedBox(height: 16),
            Text(
              "From 19:00 ET you're the only confirmed physician here. Your clinical lead is arranging a second.",
            ),
          ],
        ),
        const PreviewCard(
          children: [
            PreviewHeading('Next shift'),
            Text('Not in this roster yet'),
          ],
        ),
      ],
    ],
  );
}
