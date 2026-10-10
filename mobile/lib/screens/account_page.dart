import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../data/api.dart';
import 'data_widgets.dart';
import 'shared.dart';

class AccountPage extends StatefulWidget {
  const AccountPage({super.key, required this.services, required this.me});
  final AppServices services;
  final Me me;
  @override
  State<AccountPage> createState() => _AccountPageState();
}

class _AccountPageState extends State<AccountPage> {
  bool _busy = false;
  String? _error;
  Future<void> _optIn(bool value) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.services.auth.setOptIn(value);
      if (!mounted) return;
      if (result.outcome == PreferencesOutcome.openOfferExists) {
        final confirmed = await confirmAction(
          context,
          title: 'You have an open request.',
          message: 'Decline it and opt out?',
          confirmLabel: 'Decline and opt out',
        );
        if (!mounted) return;
        if (confirmed) {
          await widget.services.auth.setOptIn(false, declineOpenOffer: true);
        }
      }
      await widget.services.physicianFeed.refreshNow();
    } catch (error) {
      if (mounted) setState(() => _error = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sound() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.services.alerts.enableSound();
      if (mounted && !widget.services.alerts.soundEnabled) {
        setState(
          () => _error =
              'Sound could not be enabled. Tap Enable sound to try again.',
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _signOut() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.services.auth.signOut();
    } catch (error) {
      if (mounted) setState(() => _error = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ScreenBody(
    children: [
      SectionTitle(widget.me.displayName),
      Text(widget.me.role == Role.physician ? 'Physician' : 'Clinical lead'),
      const SizedBox(height: 20),
      if (widget.me.role == Role.physician)
        SwitchListTile.adaptive(
          title: const Text('Available for extra shifts'),
          value: widget.me.splitShiftOptIn == true,
          onChanged: _busy || !widget.me.can('preferences.update')
              ? null
              : _optIn,
        ),
      if (_error != null) Notice(_error!, isError: true),
      if (_busy)
        const Center(
          child: CircularProgressIndicator(
            semanticsLabel: 'Saving account change',
          ),
        ),
      FilledButton(
        onPressed: _busy || !kIsWeb ? null : _sound,
        child: Text(
          widget.services.alerts.soundEnabled
              ? 'Sound enabled'
              : 'Enable sound',
        ),
      ),
      if (!kIsWeb)
        const Text(
          'Chime and vibration are available in the web app. Native phone alerts are not enabled.',
        ),
      const SizedBox(height: 16),
      OutlinedButton(
        onPressed: _busy ? null : _signOut,
        child: const Text('Sign out'),
      ),
      const SizedBox(height: 24),
      const Text('Synthetic data only'),
    ],
  );
}
