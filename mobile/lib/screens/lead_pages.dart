import 'package:flutter/material.dart';
import '../data/api.dart';
import 'data_widgets.dart';
import 'shared.dart';

class ApprovalsPage extends StatelessWidget {
  const ApprovalsPage({
    super.key,
    required this.services,
    required this.me,
    required this.openProposal,
  });
  final AppServices services;
  final Me me;
  final ValueChanged<String> openProposal;
  @override
  Widget build(BuildContext context) => FeedView<LeadQueue>(
    feed: services.leadFeed.queue,
    refresh: services.leadFeed.refreshNow,
    builder: (context, queue) => ScreenBody(
      children: [
        ClockBuilder(
          clock: services.clock,
          builder: (_) => Text(formatEtHeader(services.clock.now())),
        ),
        SectionTitle('${queue.pendingCount} waiting'),
        for (final proposal in queue.proposals)
          DataCard(
            children: [
              Text('Waiting for you · gap at ${formatEtLabel(proposal.start)}'),
              SectionTitle(
                '${proposal.recipientCount} physician${proposal.recipientCount == 1 ? '' : 's'} for ${hospitalsLabel(proposal.hospitals)}',
              ),
              Text(formatEtRange(proposal.start, proposal.end)),
              TextButton(
                onPressed: () => openProposal(proposal.proposalId),
                child: const Text('Review proposal'),
              ),
            ],
          ),
        for (final escalation in queue.escalations)
          EscalationCard(
            key: ValueKey(escalation.escalationId),
            services: services,
            me: me,
            escalation: escalation,
          ),
        if (queue.pendingCount == 0)
          const Text('No decisions waiting for you.'),
        const SectionTitle('Sent'),
        ValueListenableBuilder<FeedState<BroadcastList>>(
          valueListenable: services.leadFeed.activeOffers,
          builder: (context, state, _) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (state.loading)
                const LinearProgressIndicator(
                  semanticsLabel: 'Loading sent offers',
                ),
              if (state.error != null) ...[
                Notice(state.stale ? 'Reconnecting…' : errorText(state.error!)),
                TextButton(
                  onPressed: services.leadFeed.refreshNow,
                  child: const Text('Retry sent offers'),
                ),
              ],
              for (final broadcast in state.data?.broadcasts ?? <Broadcast>[])
                DataCard(
                  children: [
                    SectionTitle(hospitalsLabel(broadcast.hospitals)),
                    Text(
                      '${formatEtRange(broadcast.start, broadcast.end)} · ${switch (broadcast.status) {
                        BroadcastStatus.open => 'Open',
                        BroadcastStatus.filled => 'Filled',
                        BroadcastStatus.unfilled => 'Unfilled',
                      }}',
                    ),
                    if (broadcast.filledBy != null)
                      Text('Filled by ${broadcast.filledBy!.displayName}'),
                    for (final offer in broadcast.offers)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${offer.displayName} · ${offerLabel(offer.status, offer.statusReason)}',
                            ),
                            if (offer.status == OfferStatus.sent)
                              ClockBuilder(
                                clock: services.clock,
                                builder: (_) => Text(
                                  '${formatCountdown(services.clock.remaining(offer.expiresAt))} left',
                                ),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
              if (state.data?.broadcasts.isEmpty == true)
                const Text('No sent requests.'),
            ],
          ),
        ),
        const SectionTitle('Done automatically'),
        for (final action in queue.automatedActions)
          DataCard(
            children: [Text('${formatEtLabel(action.at)} · ${action.text}')],
          ),
      ],
    ),
  );
}

class EscalationCard extends StatefulWidget {
  const EscalationCard({
    super.key,
    required this.services,
    required this.me,
    required this.escalation,
  });
  final AppServices services;
  final Me me;
  final Escalation escalation;
  @override
  State<EscalationCard> createState() => _EscalationCardState();
}

class _EscalationCardState extends State<EscalationCard> {
  bool _busy = false;
  String? _message;
  bool _failed = false;
  bool _done = false;
  Future<void> _authorize() async {
    if (_busy ||
        _done ||
        !(widget.services.auth.me.value ?? widget.me).can(
          'escalation.authorize',
        )) {
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final confirm = await confirmAction(
        context,
        title: 'Authorize intervention?',
        message: widget.escalation.proposedIntervention,
        confirmLabel: 'Authorize',
      );
      if (!mounted || !confirm) return;
      if (!(widget.services.auth.me.value ?? widget.me).can(
        'escalation.authorize',
      )) {
        return;
      }
      final result = await widget.services.lead.authorize(
        widget.escalation.escalationId,
      );
      if (!mounted) return;
      setState(() {
        _done = true;
        _failed = false;
        _message = result.outcome == EscalationOutcome.authorized
            ? 'Authorized'
            : 'Already authorized';
      });
      await widget.services.leadFeed.refreshNow();
    } catch (error) {
      if (mounted) {
        setState(() {
          _message = errorText(error);
          _failed = true;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => DataCard(
    children: [
      SectionTitle(widget.escalation.hospitalName),
      Text(widget.escalation.reason),
      const SizedBox(height: 12),
      Text(widget.escalation.proposedIntervention),
      if (_message != null) Notice(_message!, isError: _failed),
      if (widget.me.can('escalation.authorize') && !_done)
        FilledButton(
          onPressed: _busy ? null : _authorize,
          child: _busy
              ? const SizedBox.square(
                  dimension: 22,
                  child: CircularProgressIndicator(
                    semanticsLabel: 'Authorizing',
                  ),
                )
              : const Text('Authorize'),
        ),
    ],
  );
}

class ProposalScreen extends StatefulWidget {
  const ProposalScreen({
    super.key,
    required this.services,
    required this.proposalId,
  });
  final AppServices services;
  final String proposalId;
  @override
  State<ProposalScreen> createState() => _ProposalScreenState();
}

class _ProposalScreenState extends State<ProposalScreen> {
  Proposal? _proposal;
  ProposalActionResult? _result;
  Object? _error;
  String? _actionError;
  bool _busy = false;
  bool _loading = false;
  bool _rejecting = false;
  int _revision = 0;
  final _reason = TextEditingController();
  late final Poller _poller;
  AppServices get s => widget.services;
  @override
  void initState() {
    super.initState();
    _poller = Poller(const Duration(seconds: 5), _load)..start();
  }

  Future<void> _load() async {
    if (_loading || _busy) return;
    _loading = true;
    final revision = _revision;
    try {
      final proposal = await s.lead.proposal(widget.proposalId);
      if (mounted && !_busy && revision == _revision) {
        setState(() {
          _proposal = proposal;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted && revision == _revision) setState(() => _error = error);
    } finally {
      _loading = false;
    }
  }

  Future<void> _decide(bool approve) async {
    final permission = approve ? 'proposal.approve' : 'proposal.reject';
    if (_busy ||
        _proposal?.status != ProposalStatus.proposed ||
        s.auth.me.value?.can(permission) != true ||
        (!approve && _reason.text.trim().isEmpty)) {
      return;
    }
    setState(() {
      _busy = true;
      _actionError = null;
      _revision++;
    });
    try {
      final confirmed = await confirmAction(
        context,
        title: approve ? 'Approve and send?' : 'Reject this proposal?',
        message: approve
            ? 'Send the coverage request to ${_proposal!.recipients.length} physician${_proposal!.recipients.length == 1 ? '' : 's'}.'
            : _reason.text.trim(),
        confirmLabel: approve ? 'Approve and send' : 'Confirm rejection',
      );
      if (!mounted || !confirmed) return;
      if (s.auth.me.value?.can(permission) != true) return;
      final result = await (approve
          ? s.lead.approve(widget.proposalId)
          : s.lead.reject(widget.proposalId, _reason.text.trim()));
      if (!mounted) return;
      setState(() {
        _result = result;
        _proposal = result.proposal;
      });
      await s.leadFeed.refreshNow();
    } catch (error) {
      if (mounted) setState(() => _actionError = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _open(Widget page) =>
      Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  @override
  void dispose() {
    _poller.stop();
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final proposal = _proposal;
    if (proposal == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Proposal')),
        body: _error == null
            ? const Center(child: CircularProgressIndicator())
            : DataFailure(error: _error!, retry: _load),
      );
    }
    final grouped = <String, List<String>>{};
    for (final excluded in proposal.excluded) {
      grouped.putIfAbsent(excluded.detail, () => []).add(excluded.displayName);
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Review proposal')),
      body: ValueListenableBuilder<Me?>(
        valueListenable: s.auth.me,
        builder: (context, me, _) => ScreenBody(
          children: [
            if (_error != null) ...[
              const Notice('Reconnecting…'),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
            Text(
              '${proposal.status.wire} · gap at ${formatEtLabel(proposal.gap.start)}',
            ),
            SectionTitle(
              '${proposal.recipients.length == 1 ? proposal.recipients.first.displayName : '${proposal.recipients.length} physicians'} for ${hospitalsLabel(proposal.gap.hospitals)}',
            ),
            Text(
              '${formatEtRange(proposal.gap.start, proposal.gap.end)} · ${proposal.gap.hours} hours · off shift',
            ),
            const SectionTitle('Coverage before / after'),
            for (var i = 0; i < proposal.coveragePreview.times.length; i++)
              DataCard(
                children: [
                  Text(formatEtLabel(proposal.coveragePreview.times[i])),
                  if (i < proposal.coveragePreview.without.length)
                    Text(
                      'Without: ${proposal.coveragePreview.without[i].staffed}/${proposal.coveragePreview.without[i].required}',
                    ),
                  if (i < proposal.coveragePreview.withOffer.length)
                    Text(
                      'With: ${proposal.coveragePreview.withOffer[i].staffed}/${proposal.coveragePreview.withOffer[i].required}',
                    ),
                ],
              ),
            SectionTitle(
              'Checked ${proposal.recipients.length + proposal.excluded.length} off-shift physicians',
            ),
            for (final recipient in proposal.recipients)
              DataCard(
                children: [
                  Text(
                    '${recipient.displayName} · selected${recipient.rank == null ? '' : ' · rank ${recipient.rank}'}',
                  ),
                  Text(recipient.rankReason),
                ],
              ),
            for (final entry in grouped.entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text('${entry.value.join(', ')}: ${entry.key}'),
              ),
            OutlinedButton(
              onPressed: () =>
                  _open(CandidatesScreen(services: s, gapId: proposal.gapId)),
              child: const Text('See all candidates'),
            ),
            TextButton(
              onPressed: () =>
                  _open(TrapCheckScreen(services: s, gapId: proposal.gapId)),
              child: Text('Trap check: ${proposal.trapCheck.result.wire}'),
            ),
            Text(proposal.trapCheck.explanation),
            if (me?.can('audit.read') == true)
              TextButton(
                onPressed: () =>
                    _open(AuditScreen(services: s, gapId: proposal.gapId)),
                child: const Text('View audit log'),
              ),
            if (_result != null) ...[
              Notice(switch (_result!.outcome) {
                ProposalOutcome.approved => 'Approved',
                ProposalOutcome.rejected => 'Rejected',
                ProposalOutcome.cancelled => 'Cancelled at the server recheck',
                ProposalOutcome.alreadyDecided =>
                  'Already decided. Nothing changed.',
              }),
              if (proposal.decisionReason != null)
                Text(proposal.decisionReason!),
              for (final skipped in _result!.skipped)
                Text(
                  'Skipped ${skipped.displayName}: ${skipped.failedRule} · ${skipped.detail}',
                ),
            ],
            if (_actionError != null) Notice(_actionError!, isError: true),
            if (_busy)
              const Center(
                child: CircularProgressIndicator(
                  semanticsLabel: 'Sending decision',
                ),
              ),
            if (proposal.status == ProposalStatus.proposed) ...[
              if (me?.can('proposal.approve') == true)
                FilledButton(
                  onPressed: _busy ? null : () => _decide(true),
                  child: Text(
                    proposal.recipients.length == 1
                        ? 'Approve and send to ${proposal.recipients.first.displayName}'
                        : 'Approve and send to ${proposal.recipients.length} physicians',
                  ),
                ),
              if (me?.can('proposal.reject') == true) ...[
                if (!_rejecting)
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => setState(() => _rejecting = true),
                    child: const Text('Reject'),
                  )
                else ...[
                  const SizedBox(height: 16),
                  TextField(
                    controller: _reason,
                    enabled: !_busy,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Reason for rejection',
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  OutlinedButton(
                    onPressed: _busy || _reason.text.trim().isEmpty
                        ? null
                        : () => _decide(false),
                    child: const Text('Reject proposal'),
                  ),
                ],
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class CandidatesScreen extends StatelessWidget {
  const CandidatesScreen({
    super.key,
    required this.services,
    required this.gapId,
  });
  final AppServices services;
  final String gapId;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('All candidates')),
    body: RepositoryView<CandidateList>(
      load: () => services.lead.candidates(gapId),
      interval: const Duration(seconds: 5),
      builder: (context, list) => ScreenBody(
        children: [
          Text('Evaluated ${formatEtHeader(list.evaluatedAt)}'),
          for (final candidate in list.candidates)
            DataCard(
              children: [
                SectionTitle(candidate.displayName),
                Text(
                  candidate.eligible
                      ? 'Eligible${candidate.rank == null ? '' : ' · rank ${candidate.rank}'}'
                      : 'Excluded',
                ),
                for (final rule in candidate.rules)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${rule.rule} · ${rule.name} · ${rule.passed ? 'Pass' : 'Fail'}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        Text(rule.detail),
                      ],
                    ),
                  ),
              ],
            ),
        ],
      ),
    ),
  );
}

class TrapCheckScreen extends StatelessWidget {
  const TrapCheckScreen({
    super.key,
    required this.services,
    required this.gapId,
  });
  final AppServices services;
  final String gapId;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Trap check')),
    body: RepositoryView<TrapCheck>(
      load: () => services.lead.trapCheck(gapId),
      builder: (context, check) => ScreenBody(
        children: [
          SectionTitle(check.result == CheckResult.pass ? 'Passed' : 'Failed'),
          Text(check.explanation),
          Text('Seed consults: ${check.seedConsults}'),
          Text('Joiner projected consults: ${check.joinerProjectedConsults}'),
          Text(
            'Busiest peer projected consults: ${check.busiestPeerProjectedConsults}',
          ),
        ],
      ),
    ),
  );
}

class AuditScreen extends StatelessWidget {
  const AuditScreen({super.key, required this.services, required this.gapId});
  final AppServices services;
  final String gapId;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Audit log')),
    body: RepositoryView<AuditLog>(
      load: () => services.lead.audit(gapId),
      builder: (context, log) => ScreenBody(
        children: [
          if (log.entries.isEmpty) const Text('No audit entries yet.'),
          for (final entry in log.entries)
            DataCard(
              children: [
                Text(formatEtHeader(entry.at)),
                SectionTitle(entry.actor),
                Text(entry.action),
                Text(entry.detail),
              ],
            ),
        ],
      ),
    ),
  );
}
