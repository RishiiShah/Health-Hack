import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../data/api.dart';
import 'shared.dart';
import 'theme.dart';

String errorText(Object error) => switch (error) {
  Forbidden() => "You don't have permission for this.",
  NotFound() => 'This item is no longer available.',
  Unauthorized() => 'Please sign in again.',
  InvalidRequest(:final message) => message,
  NetworkError() || Unavailable() => "Can't reach Sevaro",
  ParseError() => 'Sevaro returned data this app could not read.',
  _ => 'Something went wrong. Please try again.',
};

class DataFailure extends StatelessWidget {
  const DataFailure({super.key, required this.error, required this.retry});
  final Object error;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      Notice(errorText(error), isError: true),
      const SizedBox(height: 16),
      FilledButton(onPressed: retry, child: const Text('Retry')),
    ],
  );
}

class DataCard extends StatelessWidget {
  const DataCard({super.key, required this.children, this.color});
  final List<Widget> children;
  final Color? color;
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(18),
    decoration: OverlapStyle.panel(color: color ?? Colors.white),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Text(
      text,
      style: Theme.of(
        context,
      ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
    ),
  );
}

/// Mounted only for the active tab. Last-good data survives refresh failures.
class RepositoryView<T> extends StatefulWidget {
  const RepositoryView({
    super.key,
    required this.load,
    required this.builder,
    this.interval,
  });
  final Future<T> Function() load;
  final Widget Function(BuildContext, T) builder;
  final Duration? interval;
  @override
  State<RepositoryView<T>> createState() => _RepositoryViewState<T>();
}

class _RepositoryViewState<T> extends State<RepositoryView<T>> {
  T? _data;
  Object? _error;
  bool _busy = false;
  Poller? _poller;
  @override
  void initState() {
    super.initState();
    if (widget.interval != null) {
      _poller = Poller(widget.interval!, _load)..start();
    } else {
      _load();
    }
  }

  Future<void> _load() async {
    if (_busy) return;
    _busy = true;
    try {
      final value = await widget.load();
      if (mounted) {
        setState(() {
          _data = value;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      _busy = false;
    }
  }

  @override
  void dispose() {
    _poller?.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_data == null) {
      if (_error != null) return DataFailure(error: _error!, retry: _load);
      return const Center(
        child: CircularProgressIndicator(semanticsLabel: 'Loading'),
      );
    }
    return Column(
      children: [
        if (_error != null)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                Expanded(child: Notice('Reconnecting… ${errorText(_error!)}')),
                TextButton(onPressed: _load, child: const Text('Retry')),
              ],
            ),
          ),
        Expanded(child: widget.builder(context, _data as T)),
      ],
    );
  }
}

class FeedView<T> extends StatelessWidget {
  const FeedView({
    super.key,
    required this.feed,
    required this.refresh,
    required this.builder,
  });
  final ValueListenable<FeedState<T>> feed;
  final Future<void> Function() refresh;
  final Widget Function(BuildContext, T) builder;
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<FeedState<T>>(
    valueListenable: feed,
    builder: (context, state, _) {
      if (state.data == null) {
        return state.error == null
            ? const Center(
                child: CircularProgressIndicator(semanticsLabel: 'Loading'),
              )
            : DataFailure(error: state.error!, retry: refresh);
      }
      return Column(
        children: [
          if (state.stale)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: Notice('Reconnecting… ${errorText(state.error!)}'),
                  ),
                  TextButton(onPressed: refresh, child: const Text('Retry')),
                ],
              ),
            ),
          Expanded(child: builder(context, state.data as T)),
        ],
      );
    },
  );
}

class ClockBuilder extends StatelessWidget {
  const ClockBuilder({super.key, required this.clock, required this.builder});
  final ServerClock clock;
  final WidgetBuilder builder;
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<DateTime>(
    valueListenable: clock.ticks,
    builder: (context, _, child) => builder(context),
  );
}

String hospitalsLabel(List<Hospital> hospitals) =>
    hospitals.map((h) => h.name).join(', ');
String offerLabel(OfferStatus status, StatusReason? reason) => switch (status) {
  OfferStatus.sent => 'New request',
  OfferStatus.accepted => "You're on",
  OfferStatus.declined => 'Declined',
  OfferStatus.expired => 'Missed',
  OfferStatus.released => 'Released',
  OfferStatus.withdrawn =>
    reason == StatusReason.filledByAnotherPhysician
        ? 'Already filled'
        : 'No longer needed',
};
