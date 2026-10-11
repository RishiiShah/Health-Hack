import 'package:flutter/material.dart';

import 'shared.dart';
import 'theme.dart';

/// Pass the role from Me, never the sign-in screen's subtitle selection.
/// Only the visible tab is mounted, so tab-owned pollers can stop in dispose.
class RoleHome extends StatefulWidget {
  const RoleHome({
    super.key,
    required this.role,
    required this.physicianPages,
    required this.leadPages,
    this.onOpenWebDashboard,
    this.initialIndex = 0,
    this.actions = const [],
    this.tabIndex,
  }) : assert(physicianPages.length == 4),
       assert(leadPages.length == 4),
       assert(initialIndex >= 0 && initialIndex < 4);

  final String role;
  final List<WidgetBuilder> physicianPages;
  final List<WidgetBuilder> leadPages;
  final VoidCallback? onOpenWebDashboard;
  final int initialIndex;
  final List<Widget> actions;
  final ValueNotifier<int>? tabIndex;

  @override
  State<RoleHome> createState() => _RoleHomeState();
}

class _RoleHomeState extends State<RoleHome> {
  late int _index = widget.initialIndex;
  @override
  void initState() {
    super.initState();
    widget.tabIndex?.addListener(_externalTab);
  }

  void _externalTab() {
    final index = widget.tabIndex?.value;
    if (index != null && index >= 0 && index < 4 && index != _index) {
      setState(() => _index = index);
    }
  }

  void _select(int index) {
    setState(() => _index = index);
    widget.tabIndex?.value = index;
  }

  @override
  void dispose() {
    widget.tabIndex?.removeListener(_externalTab);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant RoleHome oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tabIndex != widget.tabIndex) {
      oldWidget.tabIndex?.removeListener(_externalTab);
      widget.tabIndex?.addListener(_externalTab);
    }
    if (oldWidget.role != widget.role) _index = 0;
  }

  @override
  Widget build(BuildContext context) {
    if (widget.role == 'coordinator' || widget.role == 'admin') {
      return Scaffold(
        appBar: AppBar(title: const Text('Sevaro'), actions: widget.actions),
        body: ScreenBody(
          children: [
            Text(
              'Use the web dashboard',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            const Text('Your workspace is available on the web dashboard.'),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: widget.onOpenWebDashboard,
              child: const Text('Open web dashboard'),
            ),
          ],
        ),
      );
    }
    if (widget.role != 'physician' && widget.role != 'clinical_lead') {
      return const ErrorScreen(
        message: 'This account has an unrecognized role.',
      );
    }
    final physician = widget.role == 'physician';
    final labels = physician
        ? ['My shift', 'Schedule', 'Offers', 'Account']
        : ['Approvals', 'Schedule', 'Coverage', 'Account'];
    final pages = physician ? widget.physicianPages : widget.leadPages;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                decoration: OverlapStyle.panel(radius: 28),
                child: Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    const OverlapBrand(),
                    Text(
                      physician
                          ? 'Physician workspace'
                          : 'Clinical lead workspace',
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                        fontSize: 12,
                        color: OverlapStyle.muted,
                      ),
                    ),
                    ...widget.actions,
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: OverlapStyle.panel(radius: 28),
                child: LayoutBuilder(
                  builder: (context, constraints) => SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        minWidth: constraints.maxWidth,
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          for (var index = 0; index < labels.length; index++)
                            Semantics(
                              selected: _index == index,
                              child: TextButton(
                                style: TextButton.styleFrom(
                                  foregroundColor: _index == index
                                      ? Colors.white
                                      : OverlapStyle.muted,
                                  backgroundColor: _index == index
                                      ? OverlapStyle.ink
                                      : Colors.transparent,
                                  shape: const StadiumBorder(),
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 16,
                                    vertical: 12,
                                  ),
                                ),
                                onPressed: () => _select(index),
                                child: Text(
                                  labels[index],
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      physician
                          ? 'PHYSICIAN WORKSPACE'
                          : 'CLINICAL LEAD WORKSPACE',
                      style: const TextStyle(
                        fontFamily: OverlapStyle.mono,
                        color: OverlapStyle.tealDark,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: .8,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      labels[_index],
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: KeyedSubtree(
                key: ValueKey('${widget.role}/$_index'),
                child: pages[_index](context),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
