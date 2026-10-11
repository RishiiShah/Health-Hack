import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../role_home.dart';
import '../shared.dart';
import '../sign_in_screen.dart';
import 'preview_lead.dart';
import 'preview_offer.dart';
import 'preview_physician.dart';
import 'preview_widgets.dart';

class PreviewMenu extends StatelessWidget {
  const PreviewMenu({super.key});

  void _open(BuildContext context, Widget page) => Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => PreviewSurface(child: page)));

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode ||
        !const bool.fromEnvironment('SCREEN_PREVIEW', defaultValue: true)) {
      return const ErrorScreen(
        message: 'Screen previews are available only in development.',
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Screen previews')),
      body: ScreenBody(
        children: [
          const PreviewHeading(
            'Explore Sevaro',
            caption: 'DESIGN REVIEW · NO SIGN-IN NEEDED',
          ),
          const Notice(
            'Synthetic samples only. Actions stay on this device and reset when you reopen a preview.',
          ),
          const SizedBox(height: 24),
          for (final group in [
            (
              'Start here',
              <(String, String, IconData, Widget)>[
                (
                  'Physician · on shift',
                  'My shift, schedule, offers and account',
                  Icons.medical_services_outlined,
                  const PreviewDashboard(),
                ),
                (
                  'Physician · off shift',
                  'Okafor’s home and coverage requests',
                  Icons.nights_stay_outlined,
                  const PreviewDashboard(onShift: false),
                ),
                (
                  'Clinical lead',
                  'Approvals, schedule, coverage and account',
                  Icons.fact_check_outlined,
                  const PreviewDashboard(lead: true),
                ),
              ],
            ),
            (
              'Screens from the PDF',
              <(String, String, IconData, Widget)>[
                (
                  'Sign-in',
                  'Layout only; no authentication',
                  Icons.login,
                  const SignInScreen(),
                ),
                (
                  'Approvals',
                  'Approve, reject and inspect eligibility',
                  Icons.verified_outlined,
                  const PreviewDashboard(lead: true),
                ),
                (
                  'Coverage',
                  'Staffed / required and footnotes',
                  Icons.grid_view,
                  const PreviewDashboard(lead: true, initialIndex: 2),
                ),
                (
                  'Lead schedule',
                  'Day strip and team timeline',
                  Icons.calendar_month,
                  const PreviewDashboard(lead: true, initialIndex: 1),
                ),
                (
                  'My shift',
                  'Shah’s consult cards and shift summary',
                  Icons.work_outline,
                  const PreviewDashboard(),
                ),
                (
                  'Simulated lock screen',
                  'Tap the notification to open an offer',
                  Icons.notifications_outlined,
                  const PreviewLockScreen(),
                ),
                (
                  'Offer details & outcomes',
                  'Accept, decline, expire and simulate a race',
                  Icons.inbox_outlined,
                  const PreviewOffer(),
                ),
                (
                  'Accepted offer',
                  'Routing limits, next steps and release',
                  Icons.check_circle_outline,
                  const PreviewOffer(initialScenario: 'accepted'),
                ),
                (
                  'My schedule',
                  'Today, teammates and next shift',
                  Icons.date_range,
                  const PreviewDashboard(initialIndex: 1),
                ),
              ],
            ),
          ]) ...[
            PreviewHeading(group.$1),
            for (final item in group.$2)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  clipBehavior: Clip.antiAlias,
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 10,
                    ),
                    leading: Icon(item.$3, color: previewTeal),
                    title: Text(
                      item.$1,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: Text(item.$2),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _open(context, item.$4),
                  ),
                ),
              ),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class PreviewDashboard extends StatefulWidget {
  const PreviewDashboard({
    super.key,
    this.lead = false,
    this.onShift = true,
    this.initialIndex = 0,
  });
  final bool lead;
  final bool onShift;
  final int initialIndex;
  @override
  State<PreviewDashboard> createState() => _PreviewDashboardState();
}

class _PreviewDashboardState extends State<PreviewDashboard> {
  bool _optedIn = true;
  bool _sound = false;
  bool _preferencesBusy = false;

  void _open(Widget page) => Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => PreviewSurface(child: page)));

  Future<void> _setOptIn(bool value) async {
    if (_preferencesBusy) return;
    setState(() => _preferencesBusy = true);
    final confirmed =
        value ||
        await confirmAction(
          context,
          title: 'You have an open request.',
          message: 'Decline it and opt out?',
          confirmLabel: 'Decline and opt out',
        );
    if (!mounted) return;
    setState(() {
      if (confirmed) _optedIn = value;
      _preferencesBusy = false;
    });
  }

  Widget _account(BuildContext context) => ScreenBody(
    children: [
      PreviewHeading(
        widget.lead
            ? 'Clinical lead on duty'
            : widget.onShift
            ? 'Dr. Priya Shah'
            : 'Dr. Grace Okafor',
        caption: widget.lead ? 'Clinical lead' : 'Physician',
      ),
      PreviewCard(
        children: [
          if (!widget.lead)
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              title: const Text('Available for extra shifts'),
              subtitle: const Text('Preview an opt-in preference change.'),
              value: _optedIn,
              onChanged: _preferencesBusy ? null : _setOptIn,
            ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            title: const Text('Enable sound'),
            subtitle: const Text('Visual preview only; no sound will play.'),
            value: _sound,
            onChanged: (value) => setState(() => _sound = value),
          ),
        ],
      ),
      OutlinedButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Exit preview'),
      ),
      const SizedBox(height: 24),
      const Text('Synthetic data only', textAlign: TextAlign.center),
    ],
  );

  @override
  Widget build(BuildContext context) => RoleHome(
    role: widget.lead ? 'clinical_lead' : 'physician',
    initialIndex: widget.initialIndex,
    physicianPages: [
      (_) => PreviewShift(
        onShift: widget.onShift,
        onOffers: () => _open(const PreviewOffer()),
      ),
      (_) => const PreviewPhysicianSchedule(),
      (_) => PreviewOffers(optedIn: _optedIn),
      _account,
    ],
    leadPages: [
      (_) => const PreviewApprovals(),
      (_) => PreviewLeadSchedule(
        onReview: () => _open(const _StandaloneApprovals()),
      ),
      (_) => const PreviewCoverage(),
      _account,
    ],
  );
}

class _StandaloneApprovals extends StatelessWidget {
  const _StandaloneApprovals();
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Approvals')),
    body: const PreviewApprovals(),
  );
}
