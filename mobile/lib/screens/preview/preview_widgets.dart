import 'package:flutter/material.dart';
import '../theme.dart';

const previewInk = OverlapStyle.ink;
const previewTeal = OverlapStyle.teal;
const previewGreen = OverlapStyle.green;
const previewOrange = OverlapStyle.amber;

/// Used only by the debug screen gallery. Samples never leave this UI.
class PreviewSurface extends StatelessWidget {
  const PreviewSurface({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Material(
        color: previewInk,
        child: SafeArea(
          bottom: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                const Icon(
                  Icons.science_outlined,
                  color: Colors.white,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'SCREEN PREVIEW · synthetic data',
                    style: Theme.of(
                      context,
                    ).textTheme.labelMedium?.copyWith(color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      Expanded(child: child),
    ],
  );
}

class PreviewCard extends StatelessWidget {
  const PreviewCard({
    super.key,
    required this.children,
    this.accent,
    this.color = Colors.white,
  });
  final List<Widget> children;
  final Color? accent;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(
        color: accent ?? OverlapStyle.line,
        width: accent == null ? 1 : 1.5,
      ),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0A1E2530),
          blurRadius: 12,
          offset: Offset(0, 3),
        ),
      ],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

class PreviewPill extends StatelessWidget {
  const PreviewPill(this.text, {super.key, this.color = previewTeal});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.centerLeft,
    widthFactor: 1,
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontWeight: FontWeight.w700),
      ),
    ),
  );
}

class PreviewHeading extends StatelessWidget {
  const PreviewHeading(this.text, {super.key, this.caption});
  final String text;
  final String? caption;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (caption != null) ...[
          Text(caption!, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 8),
        ],
        Text(
          text,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w800,
            color: previewInk,
          ),
        ),
      ],
    ),
  );
}

class PreviewWeek extends StatelessWidget {
  const PreviewWeek({
    super.key,
    required this.selectedDay,
    required this.onSelected,
  });
  final int selectedDay;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const Align(
        alignment: Alignment.centerLeft,
        child: Text(
          'March 2026',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      const SizedBox(height: 12),
      Row(
        children: [
          for (var i = 0; i < 7; i++)
            Expanded(
              child: TextButton(
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  backgroundColor: selectedDay == i + 15
                      ? previewTeal
                      : Colors.white,
                  foregroundColor: selectedDay == i + 15
                      ? Colors.white
                      : previewInk,
                ),
                onPressed: () => onSelected(i + 15),
                child: Column(
                  children: [
                    Text(['S', 'M', 'T', 'W', 'T', 'F', 'S'][i]),
                    Text('${i + 15}'),
                  ],
                ),
              ),
            ),
        ],
      ),
      const SizedBox(height: 20),
    ],
  );
}
