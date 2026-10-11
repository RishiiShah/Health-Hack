import 'package:flutter/material.dart';

import 'shared.dart';
import 'theme.dart';

/// The parent calls auth.signIn, routes using the returned Me, and maps errors
/// to display text. Null means success; credentials are never persisted here.
typedef SignInCallback =
    Future<String?> Function(String email, String password);

class SignInScreen extends StatefulWidget {
  const SignInScreen({
    super.key,
    this.onSignIn,
    this.showDemoAccounts = true,
    this.showRoleSelection = true,
    this.notice,
    this.onPreviewRoleChanged,
  });

  final SignInCallback? onSignIn;
  final bool showDemoAccounts;
  final bool showRoleSelection;
  final String? notice;
  final ValueChanged<bool>? onPreviewRoleChanged;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _physician = true;
  bool _busy = false;
  bool _obscure = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || widget.onSignIn == null || !_form.currentState!.validate()) {
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    String? error;
    try {
      error = await widget.onSignIn!(_email.text.trim(), _password.text);
    } catch (_) {
      error = "Can't reach Sevaro. Please try again.";
    }
    if (!mounted) return;
    _password.clear();
    setState(() {
      _busy = false;
      _error = error;
    });
  }

  void _unavailable() => ScaffoldMessenger.of(
    context,
  ).showSnackBar(const SnackBar(content: Text('Not available in the demo')));

  void _selectRole(bool physician) {
    setState(() => _physician = physician);
    widget.onPreviewRoleChanged?.call(physician);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: ScreenBody(
      children: [
        const OverlapBrand(),
        const SizedBox(height: 28),
        Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 448),
            child: Container(
              padding: const EdgeInsets.all(24),
              decoration: OverlapStyle.panel(radius: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (widget.notice != null) Notice(widget.notice!),
                  Text(
                    'Welcome back',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    !widget.showRoleSelection
                        ? 'Sign in with your work account.'
                        : _physician
                        ? 'Your shifts and coverage requests, in one place.'
                        : 'Keep your team connected and coverage on track.',
                  ),
                  const SizedBox(height: 24),
                  if (widget.showRoleSelection) ...[
                    const Text('I work as'),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 12,
                      runSpacing: 8,
                      children: [
                        ChoiceChip(
                          label: Text(
                            widget.onPreviewRoleChanged == null
                                ? 'Operations'
                                : 'Clinical lead',
                          ),
                          selected: !_physician,
                          onSelected: _busy ? null : (_) => _selectRole(false),
                        ),
                        ChoiceChip(
                          label: const Text('Physician'),
                          selected: _physician,
                          onSelected: _busy ? null : (_) => _selectRole(true),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                  ],
                  Form(
                    key: _form,
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                            controller: _email,
                            enabled: !_busy,
                            decoration: const InputDecoration(
                              labelText: 'Work email',
                            ),
                            style: const TextStyle(
                              fontFamily: OverlapStyle.mono,
                              fontSize: 13,
                            ),
                            keyboardType: TextInputType.emailAddress,
                            textInputAction: TextInputAction.next,
                            autofillHints: const [AutofillHints.username],
                            autocorrect: false,
                            validator: (value) => (value ?? '').trim().isEmpty
                                ? 'Enter your email'
                                : null,
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _password,
                            enabled: !_busy,
                            obscureText: _obscure,
                            style: const TextStyle(
                              fontFamily: OverlapStyle.mono,
                              fontSize: 13,
                            ),
                            enableSuggestions: false,
                            autocorrect: false,
                            autofillHints: const [AutofillHints.password],
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submit(),
                            decoration: InputDecoration(
                              labelText: 'Password',
                              suffixIcon: IconButton(
                                tooltip: _obscure
                                    ? 'Show password'
                                    : 'Hide password',
                                onPressed: _busy
                                    ? null
                                    : () =>
                                          setState(() => _obscure = !_obscure),
                                icon: Icon(
                                  _obscure
                                      ? Icons.visibility
                                      : Icons.visibility_off,
                                ),
                              ),
                            ),
                            validator: (value) => (value ?? '').isEmpty
                                ? 'Enter your password'
                                : null,
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton(
                              onPressed: _busy ? null : _unavailable,
                              child: const Text('Forgot password?'),
                            ),
                          ),
                          if (_error != null) ...[
                            Notice(_error!, isError: true),
                            const SizedBox(height: 16),
                          ],
                          if (widget.onSignIn == null) ...[
                            const Notice('Sign-in is temporarily unavailable.'),
                            const SizedBox(height: 16),
                          ],
                          FilledButton(
                            onPressed: _busy || widget.onSignIn == null
                                ? null
                                : _submit,
                            child: _busy
                                ? const SizedBox.square(
                                    dimension: 24,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      semanticsLabel: 'Signing in',
                                    ),
                                  )
                                : const Text('Sign in'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (!widget.showRoleSelection) ...[
                    const Text("Access is based on your account's role."),
                    const SizedBox(height: 12),
                  ],
                  OutlinedButton(
                    onPressed: _busy ? null : _unavailable,
                    child: const Text('Use Sevaro single sign-on'),
                  ),
                  if (widget.showDemoAccounts) ...[
                    const SizedBox(height: 32),
                    const Text('Demo accounts'),
                    const SizedBox(height: 8),
                    const SelectableText(
                      'lead@demo.sevaro\nshah@demo.sevaro\nokafor@demo.sevaro\nbrennan@demo.sevaro\nPassword: demo',
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'Overlap Systems \u00b7 Clinical Operations',
          textAlign: TextAlign.center,
          style: TextStyle(color: OverlapStyle.muted, fontSize: 11),
        ),
        if (widget.showDemoAccounts)
          const Text('Synthetic data only', textAlign: TextAlign.center),
      ],
    ),
  );
}
