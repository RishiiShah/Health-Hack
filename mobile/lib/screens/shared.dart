import 'package:flutter/material.dart';
import 'theme.dart';

class OverlapBrand extends StatelessWidget {
  const OverlapBrand({super.key});

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      SizedBox(
        width: 30,
        height: 26,
        child: Stack(
          children: [
            Positioned(
              left: 1,
              top: 3,
              child: Transform.rotate(
                angle: .2,
                child: Container(
                  width: 12,
                  height: 20,
                  decoration: BoxDecoration(
                    color: OverlapStyle.accent,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
            ),
            Positioned(
              left: 12,
              top: 3,
              child: Transform.rotate(
                angle: .2,
                child: Container(
                  width: 12,
                  height: 20,
                  decoration: BoxDecoration(
                    color: OverlapStyle.ink,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(width: 8),
      const Text(
        'Cerevia',
        style: TextStyle(
          fontFamily: OverlapStyle.heading,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: OverlapStyle.ink,
        ),
      ),
    ],
  );
}

class ScreenBody extends StatelessWidget {
  const ScreenBody({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Align(
      alignment: Alignment.topCenter,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1280),
          child: SizedBox(
            width: double.infinity,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: children,
            ),
          ),
        ),
      ),
    ),
  );
}

class Notice extends StatelessWidget {
  const Notice(this.message, {super.key, this.isError = false});

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isError ? colors.errorContainer : colors.secondaryContainer,
          borderRadius: BorderRadius.circular(9),
          border: Border.all(
            color: isError ? OverlapStyle.redSoft : OverlapStyle.tealSoft,
          ),
        ),
        child: Text(
          message,
          style: TextStyle(
            color: isError
                ? colors.onErrorContainer
                : colors.onSecondaryContainer,
          ),
        ),
      ),
    );
  }
}

class LoadingScreen extends StatelessWidget {
  const LoadingScreen({super.key});

  @override
  Widget build(BuildContext context) => const Scaffold(
    body: Center(
      child: CircularProgressIndicator(semanticsLabel: 'Loading Cerevia'),
    ),
  );
}

class ErrorScreen extends StatelessWidget {
  const ErrorScreen({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Cerevia')),
    body: ScreenBody(
      children: [
        Notice(message, isError: true),
        if (onRetry != null) ...[
          const SizedBox(height: 16),
          FilledButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ],
    ),
  );
}

// A dialog only returns a choice. It never calls a repository.
Future<bool> confirmAction(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
}) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    ) ??
    false;
