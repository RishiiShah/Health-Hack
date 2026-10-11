import 'package:flutter/material.dart';
import '../data/api.dart';
import 'data_widgets.dart';
import 'schedule_timeline.dart';
import 'shared.dart';
import 'theme.dart';

double _hour(DateTime instant, DateTime anchor) {
  final a = toEtFields(anchor);
  return toEtFields(
        instant,
      ).difference(DateTime.utc(a.year, a.month, a.day)).inMinutes /
      60;
}

class DateNavigation extends StatelessWidget {
  const DateNavigation({
    super.key,
    required this.label,
    required this.previous,
    required this.next,
  });
  final String label;
  final VoidCallback previous;
  final VoidCallback next;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      IconButton(
        tooltip: 'Previous week',
        onPressed: previous,
        icon: const Icon(Icons.chevron_left),
      ),
      Expanded(child: Text(label, textAlign: TextAlign.center)),
      IconButton(
        tooltip: 'Next week',
        onPressed: next,
        icon: const Icon(Icons.chevron_right),
      ),
    ],
  );
}

class PhysicianSchedulePage extends StatefulWidget {
  const PhysicianSchedulePage({super.key, required this.services});
  final AppServices services;
  @override
  State<PhysicianSchedulePage> createState() => _PhysicianSchedulePageState();
}

class _PhysicianSchedulePageState extends State<PhysicianSchedulePage> {
  late DateTime _week = etWeekStart(widget.services.clock.now());
  void _move(int days) =>
      setState(() => _week = _week.add(Duration(days: days)));
  @override
  Widget build(BuildContext context) => Column(
    children: [
      DateNavigation(
        label: 'Week of ${formatDate(_week)}',
        previous: () => _move(-7),
        next: () => _move(7),
      ),
      Expanded(
        child: RepositoryView<MySchedule>(
          key: ValueKey(_week),
          load: () => widget.services.shifts.mySchedule(_week),
          builder: (context, schedule) {
            final withYou = schedule.withYou;
            return ScreenBody(
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final day in schedule.days)
                      Chip(
                        label: Text(
                          '${formatDate(day.date)}\n${day.kind == DayKind.split ? 'Extra shift' : day.kind.wire}',
                        ),
                        backgroundColor: switch (day.kind) {
                          DayKind.day => const Color(0xFFBDE9DF),
                          DayKind.night => const Color(0xFFE2E8F0),
                          DayKind.split => const Color(0xFFD9F7EF),
                          DayKind.off => const Color(0xFFEEF1F2),
                        },
                      ),
                  ],
                ),
                DataCard(
                  children: [
                    const SectionTitle('Today'),
                    Text(
                      schedule.today.status == TodayStatus.onShift
                          ? 'On shift'
                          : 'Off shift',
                    ),
                    if (schedule.today.start != null &&
                        schedule.today.end != null)
                      Text(
                        formatEtRange(
                          schedule.today.start!,
                          schedule.today.end!,
                        ),
                      ),
                    if (schedule.today.end != null)
                      ClockBuilder(
                        clock: widget.services.clock,
                        builder: (_) => Text(
                          '${formatHoursMinutes(widget.services.clock.remaining(schedule.today.end!))} left',
                        ),
                      ),
                    Text(
                      '${schedule.today.consults} consults · ${schedule.today.calls} calls · ${schedule.today.hospitals} hospitals',
                    ),
                  ],
                ),
                if (withYou != null)
                  DataCard(
                    children: [
                      SectionTitle('With you at ${withYou.hospitalName}'),
                      ClockBuilder(
                        clock: widget.services.clock,
                        builder: (_) => ScheduleTimeline(
                          startHour: _hour(
                            withYou.windowStart,
                            withYou.windowStart,
                          ),
                          endHour: _hour(
                            withYou.windowEnd,
                            withYou.windowStart,
                          ),
                          currentHour: _hour(
                            widget.services.clock.now(),
                            withYou.windowStart,
                          ),
                          currentTimeLabel: formatEt(
                            widget.services.clock.now(),
                          ),
                          entries: [
                            for (final row in withYou.rows)
                              TimelineEntry(
                                name: row.isYou
                                    ? 'You · ${row.displayName}'
                                    : row.displayName,
                                hoursLabel:
                                    '${row.label} · ${formatEtRange(row.start, row.end)}',
                                startHour: _hour(
                                  row.start,
                                  withYou.windowStart,
                                ),
                                endHour: _hour(row.end, withYou.windowStart),
                                kind: TimelineKind.day,
                                highlighted: row.isYou,
                              ),
                          ],
                        ),
                      ),
                      if (withYou.note != null) Text(withYou.note!),
                    ],
                  ),
                DataCard(
                  children: [
                    const SectionTitle('Next shift'),
                    Text(
                      schedule.nextShift == null
                          ? 'Not in this roster yet'
                          : '${formatEtDay(schedule.nextShift!.start)} · ${formatEtRange(schedule.nextShift!.start, schedule.nextShift!.end)}',
                    ),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    ],
  );
}

class LeadSchedulePage extends StatefulWidget {
  const LeadSchedulePage({
    super.key,
    required this.services,
    required this.openProposal,
  });
  final AppServices services;
  final ValueChanged<String> openProposal;
  @override
  State<LeadSchedulePage> createState() => _LeadSchedulePageState();
}

class _LeadSchedulePageState extends State<LeadSchedulePage> {
  late DateTime _date = etDate(widget.services.clock.now());
  void _move(int days) =>
      setState(() => _date = _date.add(Duration(days: days)));
  @override
  Widget build(BuildContext context) {
    final sunday = _date.subtract(Duration(days: _date.weekday % 7));
    return Column(
      children: [
        DateNavigation(
          label: formatDate(_date),
          previous: () => _move(-7),
          next: () => _move(7),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (var i = 0; i < 7; i++)
                ChoiceChip(
                  label: Text(
                    '${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][i]}\n${sunday.add(Duration(days: i)).day}',
                  ),
                  selected: _date == sunday.add(Duration(days: i)),
                  onSelected: (_) =>
                      setState(() => _date = sunday.add(Duration(days: i))),
                ),
            ],
          ),
        ),
        Expanded(
          child: RepositoryView<LeadSchedule>(
            key: ValueKey(_date),
            load: () => widget.services.lead.schedule(_date),
            builder: (context, schedule) => ScreenBody(
              children: [
                if (schedule.banner != null)
                  DataCard(
                    children: [
                      Text(schedule.banner!.text),
                      TextButton(
                        onPressed: () =>
                            widget.openProposal(schedule.banner!.proposalId),
                        child: const Text('Review proposal'),
                      ),
                    ],
                  ),
                for (final group in [
                  ('On shift · ${schedule.onShift.length}', schedule.onShift),
                  (
                    'Off shift · ${schedule.offShiftWorkingToday} of ${schedule.offShiftTotal} working today',
                    schedule.offShift,
                  ),
                ])
                  DataCard(
                    children: [
                      SectionTitle(group.$1),
                      ClockBuilder(
                        clock: widget.services.clock,
                        builder: (_) => ScheduleTimeline(
                          startHour: _hour(
                            schedule.windowStart,
                            schedule.windowStart,
                          ),
                          endHour: _hour(
                            schedule.windowEnd,
                            schedule.windowStart,
                          ),
                          currentHour: _hour(
                            widget.services.clock.now(),
                            schedule.windowStart,
                          ),
                          currentTimeLabel: formatEt(
                            widget.services.clock.now(),
                          ),
                          entries: [
                            for (final row in group.$2)
                              if (row.start != null && row.end != null)
                                TimelineEntry(
                                  name: row.displayName,
                                  hoursLabel: formatEtRange(
                                    row.start!,
                                    row.end!,
                                  ),
                                  startHour: _hour(
                                    row.start!,
                                    schedule.windowStart,
                                  ),
                                  endHour: _hour(
                                    row.end!,
                                    schedule.windowStart,
                                  ),
                                  kind: switch (row.kind) {
                                    LeadShiftKind.day => TimelineKind.day,
                                    LeadShiftKind.night => TimelineKind.night,
                                    LeadShiftKind.away => TimelineKind.away,
                                    LeadShiftKind.offer => TimelineKind.offer,
                                  },
                                ),
                          ],
                        ),
                      ),
                      for (final row in group.$2)
                        if (row.start == null || row.end == null)
                          Text(
                            '${row.displayName} · ${row.kind.wire} · no scheduled time',
                          ),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class CoveragePage extends StatelessWidget {
  const CoveragePage({super.key, required this.services});
  final AppServices services;
  @override
  Widget build(BuildContext context) => RepositoryView<CoverageBoard>(
    load: services.lead.coverage,
    interval: const Duration(seconds: 15),
    builder: (context, board) => ScreenBody(
      children: [
        const SectionTitle('Staffed / required · training data'),
        for (final row in board.hospitals)
          DataCard(
            children: [
              SectionTitle(row.name),
              Text(
                row.statusText,
                style: TextStyle(
                  color: switch (row.level) {
                    CoverageLevel.short => OverlapStyle.red,
                    CoverageLevel.covered => OverlapStyle.green,
                    _ => OverlapStyle.amber,
                  },
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 18,
                runSpacing: 12,
                children: [
                  for (
                    var i = 0;
                    i < board.columns.length && i < row.cells.length;
                    i++
                  )
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${board.columns[i].label} · ${formatEtLabel(board.columns[i].at)}',
                        ),
                        Container(
                          margin: const EdgeInsets.only(top: 6),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(4),
                            color: row.cells[i].staffed < row.cells[i].required
                                ? OverlapStyle.redSoft
                                : row.cells[i].staffed == row.cells[i].required
                                ? const Color(0xFFDBEAFE)
                                : OverlapStyle.greenSoft,
                          ),
                          child: Text(
                            '${row.cells[i].staffed}/${row.cells[i].required}${row.cells[i].marker ?? ''}',
                            style: TextStyle(
                              fontFamily: OverlapStyle.mono,
                              fontSize: 16,
                              color:
                                  row.cells[i].staffed < row.cells[i].required
                                  ? OverlapStyle.red
                                  : row.cells[i].staffed ==
                                        row.cells[i].required
                                  ? const Color(0xFF275B9A)
                                  : OverlapStyle.green,
                            ),
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ],
          ),
        for (final note in board.footnotes) Text('${note.marker} ${note.text}'),
      ],
    ),
  );
}
