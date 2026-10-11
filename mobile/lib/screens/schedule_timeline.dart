import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'theme.dart';

enum TimelineKind {
  day('Day', Color(0xFFBDE9DF)),
  night('Night', Color(0xFF1E293B)),
  away('Away', Color(0xFFEFD6A4)),
  offer('Offer', OverlapStyle.tealSoft);

  const TimelineKind(this.label, this.color);
  final String label;
  final Color color;
}

/// Display inputs only. Hours are supplied in ET by the screen's data adapter.
class TimelineEntry {
  const TimelineEntry({
    required this.name,
    required this.hoursLabel,
    required this.startHour,
    required this.endHour,
    required this.kind,
    this.highlighted = false,
  });
  final String name;
  final String hoursLabel;
  final double startHour;
  final double endHour;
  final TimelineKind kind;
  final bool highlighted;
}

class ScheduleTimeline extends StatelessWidget {
  const ScheduleTimeline({
    super.key,
    required this.entries,
    required this.startHour,
    required this.endHour,
    required this.currentHour,
    required this.currentTimeLabel,
    this.tickEvery = 3,
  }) : assert(endHour > startHour),
       assert(tickEvery > 0);

  final List<TimelineEntry> entries;
  final double startHour;
  final double endHour;
  final double currentHour;
  final String currentTimeLabel;
  final double tickEvery;

  @override
  Widget build(BuildContext context) {
    final scaler = MediaQuery.textScalerOf(context);
    final rowHeight = math.max(66.0, scaler.scale(13) * 2 + 30);
    final plotHeight = rowHeight * entries.length;
    final ticks = <double>[
      for (var hour = startHour; hour < endHour; hour += tickEvery) hour,
      endHour,
    ];
    double fraction(double hour) =>
        ((hour - startHour) / (endHour - startHour)).clamp(0, 1);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Wrap(
            spacing: 10,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Icon(
                Icons.schedule_rounded,
                size: 18,
                color: Color(0xFFDC2626),
              ),
              Text(
                '$currentTimeLabel ET',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const Text(
                'Schedule timeline',
                style: TextStyle(color: Color(0xFF687078)),
              ),
            ],
          ),
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            // Keep the shared axis within the phone viewport. Exact names and
            // ranges below the chart remain readable when a bar truncates text.
            final width = constraints.maxWidth;
            return SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: width,
                height: plotHeight + 44,
                child: Stack(
                  children: [
                    Positioned(
                      left: 0,
                      right: 0,
                      top: 0,
                      height: plotHeight,
                      child: CustomPaint(
                        painter: _TimelineGrid(
                          ticks: ticks.map(fraction).toList(),
                          now:
                              currentHour >= startHour && currentHour <= endHour
                              ? fraction(currentHour)
                              : null,
                        ),
                      ),
                    ),
                    for (var index = 0; index < entries.length; index++)
                      if (entries[index].endHour > startHour &&
                          entries[index].startHour < endHour)
                        Positioned(
                          left: fraction(entries[index].startHour) * width,
                          top: index * rowHeight + 10,
                          width: math.max(
                            1,
                            (fraction(entries[index].endHour) -
                                    fraction(entries[index].startHour)) *
                                width,
                          ),
                          height: rowHeight - 18,
                          child: Semantics(
                            label:
                                '${entries[index].name}, ${entries[index].kind.label}, ${entries[index].hoursLabel}',
                            child: Tooltip(
                              message:
                                  '${entries[index].name} · ${entries[index].hoursLabel}',
                              child: Container(
                                alignment: Alignment.centerLeft,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                ),
                                decoration: BoxDecoration(
                                  color: entries[index].kind.color,
                                  borderRadius: BorderRadius.circular(5),
                                  border: entries[index].highlighted
                                      ? Border.all(
                                          color: const Color(0xFF161E2E),
                                          width: 3,
                                        )
                                      : entries[index].kind ==
                                            TimelineKind.offer
                                      ? Border.all(color: OverlapStyle.teal)
                                      : null,
                                ),
                                child: ExcludeSemantics(
                                  child: Text(
                                    entries[index].name,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontFamily: OverlapStyle.mono,
                                      color:
                                          entries[index].kind ==
                                              TimelineKind.night
                                          ? Colors.white
                                          : entries[index].kind ==
                                                TimelineKind.away
                                          ? OverlapStyle.amber
                                          : OverlapStyle.tealDark,
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                    if (currentHour >= startHour && currentHour <= endHour)
                      Positioned(
                        left: 0,
                        right: 0,
                        top: 0,
                        height: plotHeight,
                        child: IgnorePointer(
                          child: CustomPaint(
                            painter: _NowLine(fraction(currentHour)),
                          ),
                        ),
                      ),
                    for (final tick in ticks)
                      Positioned(
                        left: (fraction(tick) * width - 19).clamp(
                          0,
                          width - 38,
                        ),
                        top: plotHeight + 10,
                        width: 38,
                        child: Text(
                          tick.toInt().toString().padLeft(2, '0'),
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 11,
                            color: (tick - currentHour).abs() < .5
                                ? const Color(0xFF161E2E)
                                : const Color(0xFF7E8388),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 16,
          runSpacing: 10,
          children: [
            for (final kind in TimelineKind.values)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: kind.color,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(kind.label, style: const TextStyle(fontSize: 12)),
                ],
              ),
          ],
        ),
        // Exact ranges remain readable even when a short bar truncates its name.
        const SizedBox(height: 16),
        for (final entry in entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(
              '${entry.name} · ${entry.kind.label} · ${entry.hoursLabel}',
              style: const TextStyle(fontSize: 12, color: Color(0xFF687078)),
            ),
          ),
      ],
    );
  }
}

class _TimelineGrid extends CustomPainter {
  _TimelineGrid({required this.ticks, required this.now});
  final List<double> ticks;
  final double? now;

  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = const Color(0xFFE4E6E6)
      ..strokeWidth = 1;
    for (final tick in ticks) {
      for (double y = 0; y < size.height; y += 10) {
        canvas.drawLine(
          Offset(tick * size.width, y),
          Offset(tick * size.width, math.min(y + 4, size.height)),
          grid,
        );
      }
    }
    if (now != null) {
      final left = now! * size.width;
      canvas.save();
      canvas.clipRect(Rect.fromLTRB(left, 0, size.width, size.height));
      final hatch = Paint()
        ..color = const Color(0xFFF2F3F2)
        ..strokeWidth = 2;
      for (double x = left - size.height; x < size.width; x += 12) {
        canvas.drawLine(
          Offset(x, size.height),
          Offset(x + size.height, 0),
          hatch,
        );
      }
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _TimelineGrid old) =>
      old.now != now || old.ticks.toString() != ticks.toString();
}

class _NowLine extends CustomPainter {
  _NowLine(this.fraction);
  final double fraction;

  @override
  void paint(Canvas canvas, Size size) {
    final x = fraction * size.width;
    final pen = Paint()
      ..color = const Color(0xFFDC2626)
      ..strokeWidth = 2;
    canvas.drawLine(Offset(x, 6), Offset(x, size.height), pen);
    canvas.drawCircle(Offset(x, 5), 5, Paint()..color = Colors.white);
    canvas.drawCircle(
      Offset(x, 5),
      5,
      Paint()
        ..color = pen.color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
    canvas.drawCircle(Offset(x, 5), 2, pen);
  }

  @override
  bool shouldRepaint(covariant _NowLine old) => fraction != old.fraction;
}
