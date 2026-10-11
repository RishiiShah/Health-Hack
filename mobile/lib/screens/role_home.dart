import 'package:flutter/material.dart';

import 'shared.dart';

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
    final icons = physician
        ? [
            Icons.work_outline,
            Icons.calendar_month,
            Icons.inbox_outlined,
            Icons.person_outline,
          ]
        : [
            Icons.fact_check_outlined,
            Icons.calendar_month,
            Icons.grid_view,
            Icons.person_outline,
          ];
    final pages = physician ? widget.physicianPages : widget.leadPages;
    return Scaffold(
      appBar: AppBar(title: Text(labels[_index]), actions: widget.actions),
      body: KeyedSubtree(
        key: ValueKey('${widget.role}/$_index'),
        child: pages[_index](context),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFFF663C),
        foregroundColor: Colors.white,
        elevation: 0,
        shape: const CircleBorder(),
        tooltip: 'Quick navigation',
        onPressed: () => showModalBottomSheet<void>(
          context: context,
          showDragHandle: true,
          builder: (sheetContext) => SafeArea(
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text(
                      'Go to',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  for (var index = 0; index < labels.length; index++)
                    ListTile(
                      leading: Icon(icons[index]),
                      title: Text(labels[index]),
                      onTap: () {
                        Navigator.pop(sheetContext);
                        _select(index);
                      },
                    ),
                ],
              ),
            ),
          ),
        ),
        child: const Icon(Icons.add, size: 30),
      ),
      bottomNavigationBar: BottomAppBar(
        color: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: const CircularNotchedRectangle(),
        notchMargin: 8,
        height: 54 + MediaQuery.textScalerOf(context).scale(11) * 3,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: Row(
          children: [
            for (var index = 0; index < labels.length; index++) ...[
              if (index == 2) const SizedBox(width: 72),
              Expanded(
                child: Semantics(
                  selected: _index == index,
                  child: TextButton(
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 2,
                        vertical: 6,
                      ),
                      foregroundColor: _index == index
                          ? const Color(0xFF0FAC88)
                          : const Color(0xFF787E84),
                      minimumSize: const Size(48, 56),
                    ),
                    onPressed: () => _select(index),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(icons[index], size: 23),
                        const SizedBox(height: 5),
                        Text(
                          labels[index],
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: _index == index
                                ? FontWeight.w700
                                : FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
