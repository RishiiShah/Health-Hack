import 'dart:async';

import 'package:flutter/material.dart';

import 'call_demo.dart';
import 'shared.dart';
import 'theme.dart';

// Mirrors origin/anish web/src (App.tsx, LandingPage.tsx, SignIn.tsx, Schedule.tsx)
// with the same static demo data. ponytail: static dummy data, swap for the
// repositories when the demo needs to run against the server.

enum DemoRole { coordinator, lead, physician }

const _roleLabel = {
  DemoRole.coordinator: 'Coordinator',
  DemoRole.lead: 'Clinical Lead',
  DemoRole.physician: 'Dr. Priya Shah',
};
const _roleEmail = {
  DemoRole.coordinator: 'coord@demo.sevaro',
  DemoRole.lead: 'lead@demo.sevaro',
  DemoRole.physician: 'shah@demo.sevaro',
};
const _nav = {
  DemoRole.coordinator: [
    'Command',
    'Consults',
    'Doctors',
    'Schedule',
    'Audit',
    'Data',
  ],
  DemoRole.lead: ['Approvals (1)', 'Audit', 'Consults', 'Data'],
  DemoRole.physician: ['My shift', 'Offers (1)', 'Settings'],
};

// ---------------------------------------------------------------- dummy data

typedef QueueItem = ({String id, String level, int score, String reason});
const List<QueueItem> _queue = [
  (
    id: 'CON-2105',
    level: 'Critical',
    score: 160,
    reason: 'Routing has failed three times',
  ),
  (
    id: 'Suncrest 19:00',
    level: 'Warning',
    score: 147,
    reason: 'Coverage gap opens in 40 minutes',
  ),
  (
    id: 'CON-2102',
    level: 'Critical',
    score: 142,
    reason: 'Past critical imaging limit',
  ),
  (
    id: 'PHY-001',
    level: 'Warning',
    score: 126,
    reason: 'Camera active but no Synapse video',
  ),
  (
    id: 'CON-2110',
    level: 'Critical',
    score: 119,
    reason: 'Physician call has not connected',
  ),
  (
    id: 'PHY-007',
    level: 'Warning',
    score: 108,
    reason: 'Helper app offline while phone rings',
  ),
  (
    id: 'CON-2112',
    level: 'Warning',
    score: 101,
    reason: 'Note remains unsigned',
  ),
  (
    id: 'CON-2114',
    level: 'Warning',
    score: 94,
    reason: 'Open consult waiting on a person',
  ),
];

typedef Consult = (
  String id,
  String hospital,
  String type,
  String stage,
  int inStage,
  int sinceCall,
  String level,
);
final List<Consult> _consults = [
  ('CON-2102', 'Suncrest', 'Stroke', 'Imaging', 26, 38, 'Critical'),
  ('CON-2105', 'Lakeside', 'Stroke', 'Routing', 21, 34, 'Critical'),
  (
    'CON-2110',
    'North Valley',
    'General Neuro',
    'Physician call',
    18,
    31,
    'Critical',
  ),
  ('CON-2112', 'Mercy West', 'Stroke', 'Note', 17, 29, 'Critical'),
  ('CON-2114', 'Suncrest', 'Stroke', 'Physician call', 12, 21, 'Warning'),
  ('CON-2104', 'Lakeside', 'General Neuro', 'Triaged', 10, 18, 'Warning'),
  ('CON-2113', 'North Valley', 'Stroke', 'Imaging', 9, 16, 'Warning'),
  ('CON-2108', 'Mercy West', 'General Neuro', 'Routing', 8, 15, 'Warning'),
  for (var i = 0; i < 10; i++)
    (
      'CON-${2115 + i}',
      const ['Suncrest', 'Lakeside', 'North Valley', 'Mercy West'][i % 4],
      i.isOdd ? 'General Neuro' : 'Stroke',
      'Triaged',
      4 + i % 4,
      7 + i,
      'Normal',
    ),
];

typedef Physician = (
  String id,
  String name,
  String status,
  String synapse,
  String camera,
  String helper,
  String workload,
  String? canTake,
);
const List<Physician> _physicians = [
  (
    'PHY-001',
    'Dr. Patel',
    'Available',
    'No video',
    'On',
    'Online',
    '0 active',
    'camera active, no session',
  ),
  (
    'PHY-002',
    'Dr. Brooks',
    'Available',
    'Ready',
    'Off',
    'Online',
    '0 active',
    null,
  ),
  (
    'PHY-003',
    'Dr. Chen',
    'In Meeting',
    'In call',
    'On',
    'Online',
    '1 active',
    'In meeting',
  ),
  (
    'PHY-004',
    'Dr. Davis',
    'Available',
    'Ready',
    'Off',
    'Online',
    '2 active',
    'At workload limit',
  ),
  (
    'PHY-005',
    'Dr. Evans',
    'Temporarily Unavailable',
    'Quiet',
    'Off',
    'Online',
    '0 active',
    'Self-reported unavailable',
  ),
  (
    'PHY-006',
    'Dr. Okafor',
    'Available',
    'Ready',
    'Off',
    'Online',
    '1 active',
    'Assigned to current gap',
  ),
  (
    'PHY-007',
    'Dr. Torres',
    'Available',
    'Ready',
    'On',
    'Offline',
    '0 active',
    'Helper app offline',
  ),
  (
    'PHY-008',
    'Dr. Singh',
    'Available',
    'Ready',
    'Off',
    'Online',
    '2 active',
    'At workload limit',
  ),
];

enum Tone { day, night, unavailable, offer, off }

typedef Doctor = ({
  String id,
  String name,
  bool onShift,
  String status,
  String bar,
  Tone tone,
  double? from,
  double? to,
  String detail,
  String avatar,
  String workload,
  String credentialed,
});
const List<Doctor> _doctors = [
  (
    id: 'PHY-001',
    name: 'Dr. Maya Patel',
    onShift: true,
    status: 'Camera on, no session',
    bar: '08:00 to 20:00',
    tone: Tone.day,
    from: 8,
    to: 20,
    detail: 'Camera active · no Synapse session',
    avatar: 'MP',
    workload: '28 h in last 7 days',
    credentialed: '3 hospitals, incl. Suncrest',
  ),
  (
    id: 'PHY-002',
    name: 'Dr. Daniel Kim',
    onShift: true,
    status: 'Video consult · 3 open',
    bar: '08:00 to 20:00',
    tone: Tone.day,
    from: 8,
    to: 20,
    detail: 'Video consult in progress',
    avatar: 'DK',
    workload: '34 h in last 7 days',
    credentialed: '5 hospitals, incl. Suncrest',
  ),
  (
    id: 'PHY-003',
    name: 'Dr. Sofia Ramirez',
    onShift: true,
    status: 'Leaves 19:00 · 3 open',
    bar: '07:00 to 19:00',
    tone: Tone.day,
    from: 7,
    to: 19,
    detail: 'Three open consults before shift end',
    avatar: 'SR',
    workload: '37 h in last 7 days',
    credentialed: '4 hospitals',
  ),
  (
    id: 'PHY-004',
    name: 'Dr. Ethan Brooks',
    onShift: true,
    status: 'Writing a note',
    bar: '09:00 to 21:00',
    tone: Tone.day,
    from: 9,
    to: 21,
    detail: 'One note in progress',
    avatar: 'EB',
    workload: '31 h in last 7 days',
    credentialed: '4 hospitals',
  ),
  (
    id: 'PHY-005',
    name: 'Dr. Priya Shah',
    onShift: true,
    status: 'On a call',
    bar: '08:00 to 20:00',
    tone: Tone.day,
    from: 8,
    to: 20,
    detail: 'On a consult call',
    avatar: 'PS',
    workload: '29 h in last 7 days',
    credentialed: '3 hospitals',
  ),
  (
    id: 'PHY-006',
    name: 'Dr. Marcus Lee',
    onShift: true,
    status: 'Leaves 19:00 · 3 open',
    bar: '07:00 to 19:00',
    tone: Tone.day,
    from: 7,
    to: 19,
    detail: 'Three open consults before shift end',
    avatar: 'ML',
    workload: '36 h in last 7 days',
    credentialed: '4 hospitals',
  ),
  (
    id: 'PHY-007',
    name: 'Dr. Elena Torres',
    onShift: true,
    status: 'Desktop agent offline',
    bar: '10:00 to 22:00',
    tone: Tone.day,
    from: 10,
    to: 22,
    detail: 'Helper app needs verification',
    avatar: 'ET',
    workload: '24 h in last 7 days',
    credentialed: '2 hospitals',
  ),
  (
    id: 'PHY-008',
    name: 'Dr. Noah Williams',
    onShift: true,
    status: 'Temporarily unavailable',
    bar: '08:00 to 20:00',
    tone: Tone.unavailable,
    from: 8,
    to: 20,
    detail: 'Unavailable until shift end',
    avatar: 'NW',
    workload: '18 h in last 7 days',
    credentialed: '3 hospitals',
  ),
  (
    id: 'PHY-009',
    name: 'Dr. Grace Okafor',
    onShift: false,
    status: 'Offer for Suncrest',
    bar: '19:00 to 23:00',
    tone: Tone.offer,
    from: 19,
    to: 23,
    detail: 'Pending clinical lead approval',
    avatar: 'GO',
    workload: '36 h in last 7 days',
    credentialed: '4 hospitals, incl. Suncrest',
  ),
  (
    id: 'PHY-010',
    name: 'Dr. Hannah Cho',
    onShift: false,
    status: 'Not signed in yet',
    bar: 'Night · from 19:00',
    tone: Tone.night,
    from: 19,
    to: 24,
    detail: 'Next night coverage',
    avatar: 'HC',
    workload: '22 h in last 7 days',
    credentialed: '2 hospitals',
  ),
  (
    id: 'PHY-011',
    name: 'Dr. Omar Haddad',
    onShift: false,
    status: 'Not opted in',
    bar: 'Night · from 20:00',
    tone: Tone.night,
    from: 20,
    to: 24,
    detail: 'Not opted into extra shifts',
    avatar: 'OH',
    workload: '20 h in last 7 days',
    credentialed: '4 hospitals',
  ),
  (
    id: 'PHY-012',
    name: 'Dr. Ben Alvarez',
    onShift: false,
    status: 'Next shift Thu 08:00',
    bar: 'Off today',
    tone: Tone.off,
    from: null,
    to: null,
    detail: 'Next shift Thursday at 08:00',
    avatar: 'BA',
    workload: '30 h in last 7 days',
    credentialed: '3 hospitals',
  ),
  (
    id: 'PHY-013',
    name: 'Dr. Lucy Brennan',
    onShift: false,
    status: 'Next shift Wed 08:00',
    bar: 'Off today',
    tone: Tone.off,
    from: null,
    to: null,
    detail: 'Next shift Wednesday at 08:00',
    avatar: 'LB',
    workload: '27 h in last 7 days',
    credentialed: '2 hospitals',
  ),
  (
    id: 'PHY-014',
    name: 'Dr. Ravi Menon',
    onShift: false,
    status: 'Next shift Thu 07:00',
    bar: 'Off today',
    tone: Tone.off,
    from: null,
    to: null,
    detail: 'Next shift Thursday at 07:00',
    avatar: 'RM',
    workload: '26 h in last 7 days',
    credentialed: '3 hospitals',
  ),
];

const _coverageHospitals = [
  'Suncrest',
  'Oak Valley',
  'Redwood Univ',
  'Cedar Ridge',
  'Northfield',
  'Lakeview',
  'Meadowlands',
  'Harbor Regional',
  'Highland Valley',
  'Westbridge',
  'Bluewater',
  'Silver Oak',
];
const _coverageTimes = [
  'Now',
  '18:30',
  '18:45',
  '19:00',
  '19:15',
  '19:30',
  '19:45',
];
const _coverageStates = [
  'above',
  'at',
  'at',
  'gap',
  'above',
  'at',
  'above',
  'at',
];
String _coverageState(int row, int col) => row == 0 && col >= 3
    ? 'gap'
    : row == 1 && col == 0
    ? 'at'
    : _coverageStates[(row + col) % _coverageStates.length];

const _autoLog = [
  ('18:20:00', 'Coverage forecast rebuilt', '12 hospitals'),
  ('18:19:10', 'Retry scheduled', 'CON-2105 · 18:25'),
  ('18:12:40', 'Duplicate event dropped', 'EVT-8841'),
  ('17:38:00', 'Consult assigned', 'CON-2114 · Brooks'),
];
const _audit = [
  ('18:20:04', 'System', 'Snapshot loaded', '18 consults, 8 physicians'),
  ('18:19:51', 'Coordinator', 'Opened attention queue', 'CON-2105 · score 160'),
  ('18:19:42', 'System', 'Coverage gap detected', 'Suncrest · 19:00'),
  ('18:19:10', 'Clinical lead', 'Offer reviewed', 'Dr. Okafor · pending'),
];

// ---------------------------------------------------------------- style bits

const _amberLine = Color(0xFFD08A2E);
const _critical = Color(0xFFA62E25);
const _criticalSoft = Color(0xFFFBE5E1);
const _warningSoft = Color(0xFFF8EBCF);

TextStyle _mono(
  double size, {
  Color color = OverlapStyle.muted,
  FontWeight? weight,
}) => TextStyle(
  fontFamily: OverlapStyle.mono,
  fontSize: size,
  color: color,
  fontWeight: weight,
);
TextStyle _head(
  double size, {
  FontWeight weight = FontWeight.w700,
  Color color = OverlapStyle.ink,
}) => TextStyle(
  fontFamily: OverlapStyle.heading,
  fontSize: size,
  fontWeight: weight,
  color: color,
  letterSpacing: -.3,
  height: 1.2,
);

Widget _eyebrow(String text) => Text(
  text.toUpperCase(),
  style: _mono(
    11,
    color: OverlapStyle.teal,
    weight: FontWeight.w700,
  ).copyWith(letterSpacing: .9),
);

Widget _badge(String text, Color fg, Color bg) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
  decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(5)),
  child: Text(
    text,
    style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600),
  ),
);
Widget _levelChip(String level) => level == 'Critical'
    ? _badge(level, _critical, _criticalSoft)
    : level == 'Warning'
    ? _badge(level, OverlapStyle.amber, _warningSoft)
    : _badge(level, const Color(0xFF3D4853), const Color(0xFFECE8E0));

class _Card extends StatelessWidget {
  const _Card({
    required this.children,
    this.top,
    this.color = Colors.white,
    this.padding = 18,
  });
  final List<Widget> children;
  final Color? top;
  final Color color;
  final double padding;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: OverlapStyle.line),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0A1E2530),
          blurRadius: 5,
          offset: Offset(0, 2),
        ),
      ],
    ),
    clipBehavior: Clip.antiAlias,
    child: Container(
      decoration: top == null
          ? null
          : BoxDecoration(
              border: Border(top: BorderSide(color: top!, width: 3)),
            ),
      padding: EdgeInsets.all(padding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    ),
  );
}

Widget _cardHead(String eyebrow, String title, [Widget? trailing]) => Padding(
  padding: const EdgeInsets.only(bottom: 12),
  child: Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (eyebrow.isNotEmpty) _eyebrow(eyebrow),
            const SizedBox(height: 3),
            Text(title, style: _head(17)),
          ],
        ),
      ),
      ?trailing,
    ],
  ),
);

Widget _title(String eyebrow, String title, String note) => Padding(
  padding: const EdgeInsets.only(bottom: 20),
  child: Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _eyebrow(eyebrow),
            const SizedBox(height: 6),
            Text(title, style: _head(28, weight: FontWeight.w800)),
          ],
        ),
      ),
      Flexible(
        child: Text(note, textAlign: TextAlign.right, style: _mono(11)),
      ),
    ],
  ),
);

/// Two columns when wide, stacked when narrow (web breakpoints ~900px).
Widget _cols(List<Widget> children, {List<int>? flex}) => LayoutBuilder(
  builder: (context, c) => c.maxWidth < 900
      ? Column(
          children: [
            for (final w in children)
              Padding(padding: const EdgeInsets.only(bottom: 16), child: w),
          ],
        )
      : Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < children.length; i++) ...[
                if (i > 0) const SizedBox(width: 16),
                Expanded(flex: flex?[i] ?? 1, child: children[i]),
              ],
            ],
          ),
        ),
);

Widget _table(List<String> headers, List<List<Widget>> rows) =>
    SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowHeight: 36,
        dataRowMinHeight: 40,
        dataRowMaxHeight: 52,
        horizontalMargin: 6,
        columnSpacing: 18,
        headingTextStyle: const TextStyle(
          color: OverlapStyle.muted,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
        dataTextStyle: const TextStyle(color: OverlapStyle.ink, fontSize: 12),
        dividerThickness: 1,
        columns: [for (final h in headers) DataColumn(label: Text(h))],
        rows: [
          for (final r in rows)
            DataRow(cells: [for (final c in r) DataCell(c)]),
        ],
      ),
    );

ButtonStyle _pill(Color bg, Color fg, {Color? border}) =>
    FilledButton.styleFrom(
      backgroundColor: bg,
      foregroundColor: fg,
      shape: const StadiumBorder(),
      side: border == null ? null : BorderSide(color: border),
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
      textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
    );

void _toast(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

// ---------------------------------------------------------------- app flow

/// Landing → Sign in → role shell, the same flow as the web app.
class WebMirror extends StatefulWidget {
  const WebMirror({super.key});
  @override
  State<WebMirror> createState() => _WebMirrorState();
}

class _WebMirrorState extends State<WebMirror> {
  DemoRole? _role;
  bool _signIn = false;

  void _enter(DemoRole role) => setState(() => _role = role);

  @override
  Widget build(BuildContext context) {
    final role = _role;
    if (role != null) {
      return _Shell(
        role: role,
        onSignOut: () => setState(() {
          _role = null;
          _signIn = false;
        }),
      );
    }
    if (_signIn) {
      return _SignIn(
        onSignIn: _enter,
        onBack: () => setState(() => _signIn = false),
      );
    }
    return _Landing(
      onSignIn: () => setState(() => _signIn = true),
      onEnter: _enter,
    );
  }
}

class _PillBar extends StatelessWidget {
  const _PillBar({required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .92),
      borderRadius: BorderRadius.circular(999),
      border: Border.all(color: const Color(0xFFE2E8F0)),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0F000000),
          blurRadius: 24,
          offset: Offset(0, 4),
        ),
      ],
    ),
    child: Row(children: children),
  );
}

class _Landing extends StatelessWidget {
  const _Landing({required this.onSignIn, required this.onEnter});
  final VoidCallback onSignIn;
  final ValueChanged<DemoRole> onEnter;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          _PillBar(
            children: [
              const OverlapBrand(),
              const Spacer(),
              FilledButton(
                onPressed: onSignIn,
                style: _pill(OverlapStyle.ink, Colors.white),
                child: const Text('Sign in →'),
              ),
            ],
          ),
          const SizedBox(height: 48),
          Text.rich(
            textAlign: TextAlign.center,
            TextSpan(
              style: _head(40, weight: FontWeight.w800).copyWith(height: 1.1),
              children: const [
                TextSpan(text: 'Every hospital covered,\n'),
                TextSpan(
                  text: 'before',
                  style: TextStyle(
                    fontFamily: 'serif',
                    fontStyle: FontStyle.italic,
                    fontWeight: FontWeight.w400,
                    color: OverlapStyle.tealDark,
                  ),
                ),
                TextSpan(text: ' the gap opens.'),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            'Autonomous cross-timezone tele-stroke coordination across 24 emergency networks.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Color(0xFF475569),
              fontSize: 16,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 28),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton(
                onPressed: onSignIn,
                style: _pill(OverlapStyle.tealDark, Colors.white),
                child: const Text('Enter Command Center →'),
              ),
              FilledButton(
                onPressed: () => onEnter(DemoRole.physician),
                style: _pill(
                  Colors.white,
                  const Color(0xFF334155),
                  border: const Color(0xFFCBD5E1),
                ),
                child: const Text('View physician experience'),
              ),
            ],
          ),
          const SizedBox(height: 40),
          const _NetworkPreview(),
          const SizedBox(height: 48),
          Text(
            'Two workspaces, one synchronized schedule.',
            textAlign: TextAlign.center,
            style: _head(24, weight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text(
            'Continuous coordination between clinical leads and physicians.',
            textAlign: TextAlign.center,
            style: TextStyle(color: OverlapStyle.muted, fontSize: 13),
          ),
          const SizedBox(height: 24),
          _cols([
            _RoleCard(
              label: 'Coordinator & Lead Workspace',
              title: 'Command Center',
              text:
                  'Real-time triage queue ranked by clinical urgency. 90-minute predictive forecast across all regional hospital networks.',
              button: 'Sign In to Command',
              onTap: onSignIn,
            ),
            _RoleCard(
              label: 'Physician Experience',
              title: 'Mobile & Web Handoff',
              text:
                  'Clean off-shift offers without patient data. 1-tap shift acceptance with 8-rule rest verification and anti-fatigue safeguards.',
              button: 'Open Physician View',
              onTap: () => onEnter(DemoRole.physician),
            ),
          ]),
          const SizedBox(height: 16),
          Text(
            '© 2026 Overlap Systems. Intelligent Clinical Operations.',
            textAlign: TextAlign.center,
            style: _mono(11, color: const Color(0xFF94A3B8)),
          ),
        ],
      ),
    ),
  );
}

/// ponytail: stands in for the web's SVG NetworkMap; same story, plain bars.
class _NetworkPreview extends StatelessWidget {
  const _NetworkPreview();
  @override
  Widget build(BuildContext context) {
    Widget lane(
      String name,
      Color color,
      double left,
      double width, {
      bool gap = false,
    }) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            child: Text(
              name,
              style: const TextStyle(fontSize: 11, color: OverlapStyle.muted),
            ),
          ),
          Expanded(
            child: LayoutBuilder(
              builder: (context, c) => Container(
                height: 10,
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Stack(
                  children: [
                    Positioned(
                      left: c.maxWidth * left,
                      width: c.maxWidth * width,
                      top: 0,
                      bottom: 0,
                      child: Container(
                        decoration: BoxDecoration(
                          color: color,
                          borderRadius: BorderRadius.circular(999),
                          border: gap
                              ? Border.all(color: OverlapStyle.teal)
                              : null,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
    return _Card(
      padding: 22,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'ABSTRACT NETWORK VIEW',
                    style: _mono(10, color: const Color(0xFF94A3B8)),
                  ),
                  const SizedBox(height: 4),
                  Text('Network schedule', style: _head(18)),
                ],
              ),
            ),
            _badge(
              '● 24 Health Systems',
              OverlapStyle.tealDark,
              const Color(0xFFF0FDFA),
            ),
          ],
        ),
        const Divider(height: 28),
        lane('Lane A', OverlapStyle.teal, .08, .54),
        lane('Lane B', const Color(0xFF64748B), .20, .66),
        lane('Lane C', const Color(0xFFD6A24C), .48, .50),
        lane('Coverage needed', const Color(0xFF99F6E4), .10, .32, gap: true),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _badge(
              '⚡ 90-min lookahead active',
              const Color(0xFF78350F),
              const Color(0xFFFFFBEB),
            ),
            _badge(
              '✓ Shift covered',
              const Color(0xFF115E59),
              const Color(0xFFF0FDFA),
            ),
          ],
        ),
      ],
    );
  }
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({
    required this.label,
    required this.title,
    required this.text,
    required this.button,
    required this.onTap,
  });
  final String label, title, text, button;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(26),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(24),
      border: Border.all(color: OverlapStyle.line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _badge(
          label.toUpperCase(),
          const Color(0xFF115E59),
          const Color(0xFFF0FDFA),
        ),
        const SizedBox(height: 14),
        Text(title, style: _head(20)),
        const SizedBox(height: 8),
        Text(
          text,
          style: const TextStyle(
            fontSize: 13,
            color: Color(0xFF475569),
            height: 1.6,
          ),
        ),
        const Divider(height: 36),
        FilledButton(
          onPressed: onTap,
          style: FilledButton.styleFrom(
            backgroundColor: OverlapStyle.ink,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: Text('$button  →'),
        ),
      ],
    ),
  );
}

class _SignIn extends StatefulWidget {
  const _SignIn({required this.onSignIn, required this.onBack});
  final ValueChanged<DemoRole> onSignIn;
  final VoidCallback onBack;
  @override
  State<_SignIn> createState() => _SignInState();
}

class _SignInState extends State<_SignIn> {
  DemoRole _role = DemoRole.coordinator;
  final _email = TextEditingController(text: _roleEmail[DemoRole.coordinator]);
  final _password = TextEditingController(text: 'demo-password');

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  void _select(DemoRole role) => setState(() {
    _role = role;
    _email.text = _roleEmail[role]!;
  });

  @override
  Widget build(BuildContext context) {
    const roles = [
      (DemoRole.coordinator, 'Coordinator', 'Watch network, propose fixes'),
      (DemoRole.lead, 'Clinical lead', 'Approve offers & escalations'),
      (DemoRole.physician, 'Physician', 'Your shift, consults, offers'),
    ];
    const label = TextStyle(
      fontSize: 12,
      fontWeight: FontWeight.w600,
      color: Color(0xFF334155),
    );
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Row(
              children: [
                InkWell(onTap: widget.onBack, child: const OverlapBrand()),
                const Spacer(),
                TextButton(
                  onPressed: widget.onBack,
                  child: const Text(
                    '← Back to Overview',
                    style: TextStyle(fontSize: 12, color: OverlapStyle.muted),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Container(
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0xFFE2E8F0)),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x14000000),
                        blurRadius: 30,
                        offset: Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text('Sign in', style: _head(24)),
                      const SizedBox(height: 4),
                      const Text(
                        'Select your operating role to access your dashboard',
                        style: TextStyle(
                          fontSize: 12,
                          color: OverlapStyle.muted,
                        ),
                      ),
                      const SizedBox(height: 22),
                      const Text('I work as', style: label),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          for (final (role, title, text) in roles) ...[
                            if (role != DemoRole.coordinator)
                              const SizedBox(width: 8),
                            Expanded(
                              child: Semantics(
                                selected: _role == role,
                                button: true,
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(16),
                                  onTap: () => _select(role),
                                  child: Container(
                                    constraints: const BoxConstraints(
                                      minHeight: 92,
                                    ),
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: _role == role
                                          ? const Color(0xFFF0FDFA)
                                          : const Color(0xFFF8FAFC),
                                      borderRadius: BorderRadius.circular(16),
                                      border: Border.all(
                                        color: _role == role
                                            ? OverlapStyle.teal
                                            : const Color(0xFFE2E8F0),
                                        width: _role == role ? 2 : 1,
                                      ),
                                    ),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          title,
                                          style: const TextStyle(
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          text,
                                          style: const TextStyle(
                                            fontSize: 10,
                                            color: OverlapStyle.muted,
                                            height: 1.3,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 20),
                      const Text('Work email', style: label),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        style: _mono(13, color: OverlapStyle.ink),
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          const Text('Password', style: label),
                          const Spacer(),
                          InkWell(
                            onTap: () =>
                                _toast(context, 'Not available in the demo'),
                            child: const Text(
                              'Forgot it?',
                              style: TextStyle(
                                fontSize: 11,
                                color: OverlapStyle.tealDark,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      TextField(
                        controller: _password,
                        obscureText: true,
                        style: _mono(13, color: OverlapStyle.ink),
                      ),
                      const SizedBox(height: 18),
                      FilledButton(
                        onPressed: () => widget.onSignIn(_role),
                        child: Text(
                          'Sign in as ${_role == DemoRole.lead ? 'Clinical Lead' : roles[_role.index].$2}',
                        ),
                      ),
                      const Divider(height: 36),
                      const Text(
                        'Or 1-click launch into demo account:',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 11,
                          color: OverlapStyle.muted,
                        ),
                      ),
                      const SizedBox(height: 8),
                      for (final role in DemoRole.values)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Material(
                            color: const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(8),
                            child: InkWell(
                              borderRadius: BorderRadius.circular(8),
                              onTap: () => widget.onSignIn(role),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 10,
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        _roleEmail[role]!,
                                        style: _mono(
                                          12,
                                          color: const Color(0xFF1E293B),
                                        ),
                                      ),
                                    ),
                                    Text(
                                      'Launch ${role == DemoRole.coordinator
                                          ? 'Coordinator'
                                          : role == DemoRole.lead
                                          ? 'Lead'
                                          : 'Physician'} →',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                        color: OverlapStyle.tealDark,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              '© 2026 Overlap Systems. Intelligent Clinical Operations.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
            ),
          ],
        ),
      ),
    );
  }
}

class _Shell extends StatefulWidget {
  const _Shell({required this.role, required this.onSignOut});
  final DemoRole role;
  final VoidCallback onSignOut;
  @override
  State<_Shell> createState() => _ShellState();
}

class _ShellState extends State<_Shell> {
  int _page = 0;

  Widget _body() {
    final page = _nav[widget.role]![_page];
    switch (widget.role) {
      case DemoRole.coordinator:
        return switch (page) {
          'Command' => const _Command(),
          'Consults' => _ConsultsPage(
            'Coordinator workspace',
            '18 open · server-derived levels',
          ),
          'Doctors' => const _DoctorsPage(),
          'Schedule' => const _SchedulePage(),
          'Audit' => const _AuditPage(),
          _ => const _DataPage(),
        };
      case DemoRole.lead:
        return switch (page) {
          'Audit' => const _AuditPage(),
          'Consults' => _ConsultsPage(
            'Clinical lead workspace',
            'Read-only clinical view',
          ),
          'Data' => const _DataPage(),
          _ => const _Approvals(),
        };
      case DemoRole.physician:
        return switch (page) {
          'Settings' => const _PhysicianSettings(),
          'My shift' => const _MyShift(),
          _ => const _Offer(),
        };
    }
  }

  @override
  Widget build(BuildContext context) {
    final nav = _nav[widget.role]!;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
              child: Container(
                padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: .92),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x0F000000),
                      blurRadius: 24,
                      offset: Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        const OverlapBrand(),
                        const SizedBox(width: 10),
                        if (widget.role == DemoRole.coordinator)
                          Expanded(
                            child: Text(
                              '● Tue 17 Mar · 18:20 ET',
                              overflow: TextOverflow.ellipsis,
                              style: _mono(10),
                            ),
                          )
                        else
                          const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF8FAFC),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(color: const Color(0xFFE2E8F0)),
                          ),
                          child: Text(
                            _roleLabel[widget.role]!,
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFF475569),
                            ),
                          ),
                        ),
                        TextButton(
                          onPressed: widget.onSignOut,
                          child: const Text(
                            'Sign out ↗',
                            style: TextStyle(
                              fontSize: 12,
                              color: OverlapStyle.muted,
                            ),
                          ),
                        ),
                      ],
                    ),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          for (var i = 0; i < nav.length; i++)
                            Padding(
                              padding: const EdgeInsets.only(right: 4),
                              child: Semantics(
                                selected: _page == i,
                                child: TextButton(
                                  onPressed: () => setState(() => _page = i),
                                  style: TextButton.styleFrom(
                                    minimumSize: const Size(48, 36),
                                    shape: const StadiumBorder(),
                                    backgroundColor: _page == i
                                        ? OverlapStyle.ink
                                        : Colors.transparent,
                                    foregroundColor: _page == i
                                        ? Colors.white
                                        : const Color(0xFF475569),
                                    textStyle: const TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  child: Text(nav[i]),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: KeyedSubtree(
                key: ValueKey('${widget.role}/$_page'),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 24, 16, 40),
                  children: [_body()],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- coordinator

class _Command extends StatefulWidget {
  const _Command();
  @override
  State<_Command> createState() => _CommandState();
}

class _CommandState extends State<_Command> {
  String _selected = 'CON-2105';

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _title(
        'Coordinator workspace',
        'Command',
        'Replay · Tue 17 Mar · 18:20 ET',
      ),
      _cols(
        [
          _Card(
            children: [
              _cardHead(
                'Needs attention',
                'Ranked queue',
                Text('8 items', style: _mono(10)),
              ),
              const Divider(height: 1),
              for (final (index, item) in _queue.indexed)
                InkWell(
                  onTap: () => setState(() => _selected = item.id),
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 2),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 9,
                    ),
                    decoration: BoxDecoration(
                      color: _selected == item.id
                          ? const Color(0xFFEFF9F6)
                          : null,
                      borderRadius: BorderRadius.circular(6),
                      border: _selected == item.id
                          ? Border.all(color: const Color(0xFF80CBBD))
                          : const Border(
                              bottom: BorderSide(color: Color(0xFFEEEAE3)),
                            ),
                    ),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 26,
                          child: Text(
                            (index + 1).toString().padLeft(2, '0'),
                            style: _mono(12),
                          ),
                        ),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item.id,
                                style: _mono(
                                  12,
                                  color: OverlapStyle.ink,
                                  weight: FontWeight.w600,
                                ),
                              ),
                              Text(
                                item.reason,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: Color(0xFF717A82),
                                ),
                              ),
                            ],
                          ),
                        ),
                        _levelChip(item.level),
                        SizedBox(
                          width: 38,
                          child: Text(
                            '${item.score}',
                            textAlign: TextAlign.right,
                            style: _mono(12, color: _critical),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          _Dossier(item: _queue.firstWhere((q) => q.id == _selected)),
        ],
        flex: [9, 11],
      ),
      _cols(
        [
          const _CoverageMatrix(),
          const Column(
            children: [_OfferStatus(), SizedBox(height: 16), _AutoLog()],
          ),
        ],
        flex: [16, 6],
      ),
    ],
  );
}

class _Dossier extends StatelessWidget {
  const _Dossier({required this.item});
  final QueueItem item;

  @override
  Widget build(BuildContext context) {
    final rank = _queue.indexOf(item) + 1;
    Widget field(String label, String text) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: _mono(
              10,
              color: const Color(0xFF6A737A),
              weight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            text,
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF343D45),
              height: 1.55,
            ),
          ),
        ],
      ),
    );
    // ponytail: only the web's #1 item has a written dossier; others reuse its reason line.
    final top = item.id == 'CON-2105';
    return _Card(
      top: item.level == 'Critical' ? OverlapStyle.red : _amberLine,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _eyebrow('#$rank of 8 · score ${item.score} · ${item.level}'),
                  const SizedBox(height: 7),
                  Text(
                    top
                        ? 'A stroke consult has had no doctor for 10 minutes'
                        : item.reason,
                    style: _head(21),
                  ),
                ],
              ),
            ),
            const CircleAvatar(
              radius: 14,
              backgroundColor: _criticalSoft,
              child: Text(
                '!',
                style: TextStyle(color: _critical, fontWeight: FontWeight.w800),
              ),
            ),
          ],
        ),
        const Divider(height: 24),
        field(
          'Where',
          top
              ? 'Oak Valley Medical · CON-2105 · stroke · triaged at 18:09:05'
              : item.id,
        ),
        field(
          'Why it matters',
          top
              ? 'Unassigned for 10 min against a 10 min critical limit. Routing has failed 3 times because Dr. Kim is on a video consult and Dr. Williams is unavailable. Next approved doctor (Dr. Haddad) starts at 20:00.'
              : item.reason,
        ),
        field('Suggested fix', 'Escalate to the clinical lead'),
        field('Who approves', 'Clinical lead'),
        field(
          'Why this fix',
          'Escalate to the clinical lead keeps the clinical decision visible. Move to Dr. Brooks is available but would change the current routing assignment. An off-shift offer requires lead approval and adds response time.',
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: OverlapStyle.red),
              onPressed: () => _toast(context, 'Escalated to clinical lead'),
              child: const Text('Escalate to clinical lead'),
            ),
            OutlinedButton(
              onPressed: () => _toast(context, 'Reassign options: Dr. Brooks'),
              child: const Text('Check Reassign Options'),
            ),
            TextButton(
              onPressed: () {},
              child: const Text(
                'Not now',
                style: TextStyle(color: OverlapStyle.muted),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _CoverageMatrix extends StatelessWidget {
  const _CoverageMatrix();
  @override
  Widget build(BuildContext context) {
    const colors = {
      'above': (Color(0xFFD9F3E4), Color(0xFF26744F), '2 / 1'),
      'at': (Color(0xFFDBEAFE), Color(0xFF275B9A), '1 / 1'),
      'gap': (Color(0xFFFEE2E2), Color(0xFFAE3029), '0 / 1'),
    };
    Widget legend(Color c, String t) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: c,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(t, style: const TextStyle(fontSize: 10, color: Color(0xFF717A82))),
      ],
    );
    return _Card(
      children: [
        _cardHead('Next 90 minutes', 'Coverage by hospital'),
        Wrap(
          spacing: 10,
          children: [
            legend(colors['above']!.$1, 'Above min'),
            legend(colors['at']!.$1, 'At min'),
            legend(colors['gap']!.$1, 'Short'),
          ],
        ),
        const SizedBox(height: 8),
        _table(
          ['Hospital', ..._coverageTimes],
          [
            for (final (row, hospital) in _coverageHospitals.indexed)
              [
                Text(
                  hospital,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF36404A),
                  ),
                ),
                for (var col = 0; col < _coverageTimes.length; col++)
                  Builder(
                    builder: (_) {
                      final (bg, fg, label) = colors[_coverageState(row, col)]!;
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          color: bg,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(label, style: _mono(10, color: fg)),
                      );
                    },
                  ),
              ],
          ],
        ),
      ],
    );
  }
}

class _OfferStatus extends StatelessWidget {
  const _OfferStatus();
  @override
  Widget build(BuildContext context) {
    Widget dot(Color? fill) => Container(
      width: 16,
      height: 16,
      decoration: BoxDecoration(
        color: fill ?? Colors.white,
        shape: BoxShape.circle,
        border: Border.all(color: fill ?? OverlapStyle.line, width: 2),
      ),
    );
    Widget bar(Color c) => Expanded(child: Container(height: 2, color: c));
    Widget step(String bold, String rest) => Expanded(
      child: Text.rich(
        TextSpan(
          style: const TextStyle(
            fontSize: 10,
            color: Color(0xFF7B848B),
            height: 1.35,
          ),
          children: [
            TextSpan(
              text: bold,
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                color: Color(0xFF37414A),
              ),
            ),
            TextSpan(text: rest),
          ],
        ),
      ),
    );
    return _Card(
      top: _amberLine,
      color: const Color(0xFFFAF8F4),
      children: [
        Row(
          children: [
            Expanded(child: Text('Extra shift offer', style: _head(17))),
            _badge('Waiting', OverlapStyle.amber, const Color(0xFFF5E6C8)),
          ],
        ),
        const SizedBox(height: 10),
        const Text(
          'Suncrest Medical Pavilion',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        const Text(
          '19:00–23:00 ET · Dr. Okafor',
          style: TextStyle(fontSize: 13, color: OverlapStyle.muted),
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            dot(OverlapStyle.teal),
            bar(OverlapStyle.teal),
            dot(_amberLine),
            bar(OverlapStyle.line),
            dot(null),
            bar(OverlapStyle.line),
            dot(null),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            step('Proposed by you\n', '18:20:00'),
            step('Clinical lead approves\n', 'waiting'),
            step('', 'Physician response'),
          ],
        ),
      ],
    );
  }
}

class _AutoLog extends StatelessWidget {
  const _AutoLog();
  @override
  Widget build(BuildContext context) => _Card(
    children: [
      _cardHead(
        'Activity',
        'Done automatically',
        _badge('4 events', OverlapStyle.green, const Color(0xFFDCEBE2)),
      ),
      for (final (time, action, detail) in _autoLog)
        Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: const BoxDecoration(
            border: Border(top: BorderSide(color: Color(0xFFEEEAE3))),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 68,
                child: Text(
                  time,
                  style: _mono(10, color: const Color(0xFF8B9499)),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      action,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      detail,
                      style: const TextStyle(
                        fontSize: 11,
                        color: OverlapStyle.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
    ],
  );
}

class _ConsultsPage extends StatelessWidget {
  const _ConsultsPage(this.eyebrow, this.note);
  final String eyebrow, note;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title(eyebrow, 'Consults', note),
      _Card(
        children: [
          _cardHead(
            '',
            'Consult board',
            const Text(
              '18 open consults',
              style: TextStyle(fontSize: 12, color: OverlapStyle.muted),
            ),
          ),
          _table(
            [
              'Consult',
              'Hospital',
              'Type',
              'Stage',
              'In stage',
              'Since first call',
              'Level',
            ],
            [
              for (final (id, hospital, type, stage, inStage, since, level)
                  in _consults)
                [
                  Text(id, style: _mono(12, color: OverlapStyle.ink)),
                  Text(hospital),
                  Text(type),
                  Text(stage),
                  Text('$inStage min'),
                  Text('$since min'),
                  _levelChip(level),
                ],
            ],
          ),
        ],
      ),
    ],
  );
}

class _DoctorsPage extends StatelessWidget {
  const _DoctorsPage();
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title(
        'Coordinator workspace',
        'Doctors',
        '8 on shift · signal comparison',
      ),
      _Card(
        children: [
          _cardHead(
            '',
            'Physician board',
            const Text(
              'self-report beside derived read',
              style: TextStyle(fontSize: 12, color: OverlapStyle.muted),
            ),
          ),
          _table(
            [
              'Physician',
              'Self-reported',
              'Synapse',
              'Camera',
              'Helper app',
              'Workload',
              'Can take calls',
            ],
            [
              for (final (
                    id,
                    name,
                    status,
                    synapse,
                    camera,
                    helper,
                    workload,
                    canTake,
                  )
                  in _physicians)
                [
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      Text(
                        id,
                        style: const TextStyle(
                          fontSize: 11,
                          color: OverlapStyle.muted,
                        ),
                      ),
                    ],
                  ),
                  Text(status),
                  Text(synapse),
                  Text(camera),
                  Text(helper),
                  Text(workload),
                  canTake == null
                      ? _badge(
                          'Yes',
                          OverlapStyle.green,
                          const Color(0xFFDCEBE2),
                        )
                      : _badge(
                          canTake,
                          const Color(0xFF3D4853),
                          const Color(0xFFECE8E0),
                        ),
                ],
            ],
          ),
        ],
      ),
    ],
  );
}

class _SchedulePage extends StatefulWidget {
  const _SchedulePage();
  @override
  State<_SchedulePage> createState() => _SchedulePageState();
}

class _SchedulePageState extends State<_SchedulePage> {
  String _selected = 'PHY-009';
  String _filter = 'Everyone';

  bool _visible(Doctor d) => switch (_filter) {
    'On shift' => d.onShift,
    'Off shift' => !d.onShift,
    'Can cover Suncrest' => d.onShift && d.id != 'PHY-008' && d.id != 'PHY-007',
    _ => true,
  };

  Widget _row(Doctor d) {
    final (bg, fg) = switch (d.tone) {
      Tone.day => (const Color(0xFFBDE9DF), const Color(0xFF315D58)),
      Tone.night => (const Color(0xFF1E293B), const Color(0xFFD6DEEA)),
      Tone.unavailable => (const Color(0xFFF8E9C9), OverlapStyle.amber),
      Tone.offer => (const Color(0xFFD9F7EF), OverlapStyle.tealDark),
      Tone.off => (const Color(0xFFEEF1F2), const Color(0xFFA0A8AE)),
    };
    final selected = _selected == d.id;
    return InkWell(
      onTap: () => setState(() => _selected = d.id),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 5, horizontal: 5),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFFEFF9F6) : null,
          border: Border(
            left: BorderSide(
              color: selected ? OverlapStyle.teal : Colors.transparent,
              width: 3,
            ),
            bottom: const BorderSide(color: Color(0xFFF2F3F2)),
          ),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 140,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    d.name,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF33404A),
                    ),
                  ),
                  Text(
                    d.status,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 9,
                      color: Color(0xFF8A949B),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, c) {
                  // Axis is 06:00–24:00; off-shift rows fill the lane like the web.
                  final from = ((d.from ?? 6) - 6) / 18,
                      to = ((d.to ?? 24) - 6) / 18;
                  return SizedBox(
                    height: 24,
                    child: Stack(
                      children: [
                        Positioned(
                          left: c.maxWidth * from,
                          width: c.maxWidth * (to - from),
                          top: 0,
                          bottom: 0,
                          child: Container(
                            alignment: Alignment.centerLeft,
                            padding: const EdgeInsets.symmetric(horizontal: 6),
                            decoration: BoxDecoration(
                              color: bg,
                              borderRadius: BorderRadius.circular(5),
                              border: d.tone == Tone.offer
                                  ? Border.all(color: OverlapStyle.teal)
                                  : null,
                            ),
                            child: Text(
                              d.bar,
                              overflow: TextOverflow.clip,
                              maxLines: 1,
                              style: _mono(10, color: fg),
                            ),
                          ),
                        ),
                        // NOW line at 18:20.
                        Positioned(
                          left: c.maxWidth * (12.33 / 18),
                          top: 0,
                          bottom: 0,
                          child: Container(
                            width: 1,
                            color: const Color(0xFFEF4444),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final doctor = _doctors.firstWhere((d) => d.id == _selected);
    final offer = doctor.tone == Tone.offer;
    const filters = [
      ('Everyone', 14),
      ('On shift', 8),
      ('Off shift', 6),
      ('Can cover Suncrest', 7),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.chevron_left, color: OverlapStyle.muted),
            Text('Tuesday 17 March', style: _head(20)),
            const Icon(Icons.chevron_right, color: OverlapStyle.muted),
          ],
        ),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final (label, count) in filters)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    label: Text('$label  $count'),
                    selected: _filter == label,
                    showCheckmark: false,
                    selectedColor: OverlapStyle.ink,
                    labelStyle: TextStyle(
                      fontSize: 11,
                      color: _filter == label
                          ? Colors.white
                          : OverlapStyle.muted,
                    ),
                    shape: const StadiumBorder(),
                    onSelected: (_) => setState(() => _filter = label),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.fromLTRB(14, 8, 8, 8),
          decoration: BoxDecoration(
            color: OverlapStyle.ink,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  "● Suncrest is one physician short from 19:00. Dr. Okafor's offer is with the clinical lead.",
                  style: TextStyle(fontSize: 11, color: Color(0xFFDCE4EB)),
                ),
              ),
              FilledButton(
                style: FilledButton.styleFrom(
                  minimumSize: const Size(48, 32),
                  backgroundColor: OverlapStyle.teal,
                  shape: const StadiumBorder(),
                ),
                onPressed: () => setState(() => _selected = 'PHY-009'),
                child: const Text(
                  'See the offer →',
                  style: TextStyle(fontSize: 11),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _cols(
          [
            _Card(
              children: [
                _cardHead(
                  'Roster overview',
                  'Shift schedule',
                  Text('14 doctors · 18:20 ET', style: _mono(10)),
                ),
                Row(
                  children: [
                    const SizedBox(width: 145),
                    Expanded(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          for (final t in [
                            '06',
                            '09',
                            '12',
                            '15',
                            '18',
                            '21',
                            '24',
                          ])
                            Text(t, style: _mono(10)),
                        ],
                      ),
                    ),
                  ],
                ),
                for (final group in [true, false]) ...[
                  const SizedBox(height: 14),
                  Text(
                    '${group ? 'ON SHIFT' : 'OFF SHIFT'}  ·  ${_doctors.where((d) => d.onShift == group && _visible(d)).length} doctors',
                    style: _mono(10, weight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  for (final d in _doctors.where(
                    (d) => d.onShift == group && _visible(d),
                  ))
                    _row(d),
                ],
              ],
            ),
            _Card(
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      radius: 20,
                      backgroundColor: const Color(0xFFD9F7EF),
                      child: Text(
                        doctor.avatar,
                        style: _mono(
                          12,
                          color: OverlapStyle.tealDark,
                          weight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(doctor.name, style: _head(16)),
                          Text(doctor.id, style: _mono(10)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                offer
                    ? _badge(
                        'Off shift, offer pending',
                        const Color(0xFF92400E),
                        const Color(0xFFFEF3C7),
                      )
                    : _badge(
                        doctor.status,
                        const Color(0xFF5F6B74),
                        const Color(0xFFEEF1F2),
                      ),
                const SizedBox(height: 8),
                for (final (k, v) in [
                  (
                    'Today',
                    offer ? 'Offer · Suncrest 19:00 to 23:00' : doctor.detail,
                  ),
                  ('Workload', doctor.workload),
                  ('Credentialed at', doctor.credentialed),
                ])
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 9),
                    decoration: const BoxDecoration(
                      border: Border(
                        bottom: BorderSide(color: Color(0xFFF0F1EF)),
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 96,
                          child: Text(
                            k,
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFF89939A),
                            ),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            v,
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFF3E4952),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: OverlapStyle.teal,
                    ),
                    onPressed: () => _toast(
                      context,
                      offer ? 'Offer is with the clinical lead' : doctor.detail,
                    ),
                    child: Text(offer ? 'Review offer' : 'View doctor'),
                  ),
                ),
              ],
            ),
          ],
          flex: [3, 1],
        ),
      ],
    );
  }
}

class _AuditPage extends StatelessWidget {
  const _AuditPage();
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title('Immutable record', 'Audit', '18:20 ET · replay snapshot'),
      _Card(
        color: const Color(0xFFFAF8F4),
        children: [
          for (final (time, actor, action, detail) in _audit)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 13),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: OverlapStyle.line)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(width: 72, child: Text(time, style: _mono(12))),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          actor,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          action,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          detail,
                          style: const TextStyle(
                            fontSize: 12,
                            color: OverlapStyle.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    ],
  );
}

class _DataPage extends StatefulWidget {
  const _DataPage();
  @override
  State<_DataPage> createState() => _DataPageState();
}

class _DataPageState extends State<_DataPage> {
  bool _uploaded = false;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title('Coordinator workspace', 'Data', 'Static replay dataset'),
      InkWell(
        onTap: () => setState(() => _uploaded = true),
        child: Container(
          height: 250,
          width: double.infinity,
          decoration: BoxDecoration(
            color: const Color(0xFFFAF8F4),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: OverlapStyle.line, width: 1.5),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const CircleAvatar(
                radius: 21,
                backgroundColor: Color(0xFFDDEBEA),
                child: Text(
                  '↑',
                  style: TextStyle(fontSize: 22, color: OverlapStyle.teal),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                _uploaded ? 'Mock upload accepted' : 'Drop a CSV here',
                style: _head(19),
              ),
              const SizedBox(height: 4),
              Text(
                _uploaded
                    ? 'events.csv · 128 rows · 0 conflicts'
                    : 'or tap to browse · feedback is simulated locally',
                style: const TextStyle(fontSize: 13, color: OverlapStyle.muted),
              ),
              if (_uploaded) ...[
                const SizedBox(height: 10),
                _badge(
                  'Ready for review',
                  OverlapStyle.green,
                  const Color(0xFFDCEBE2),
                ),
              ],
            ],
          ),
        ),
      ),
    ],
  );
}

// ---------------------------------------------------------------- lead

class _Approvals extends StatefulWidget {
  const _Approvals();
  @override
  State<_Approvals> createState() => _ApprovalsState();
}

class _ApprovalsState extends State<_Approvals> {
  String? _decision;
  bool _overridden = false;

  Future<void> _reject() async {
    final note = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject offer'),
        content: TextField(
          controller: note,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Note (required)'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, note.text.trim().isNotEmpty),
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    note.dispose();
    if (ok == true && mounted) setState(() => _decision = 'Rejected');
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _title(
        'Clinical lead workspace',
        'Approvals',
        _decision == null ? '1 pending decision' : '0 pending decisions',
      ),
      Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFFFFF9EB),
          border: Border.all(color: const Color(0xFFE7D7B1)),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _badge(
              'Coverage impact',
              OverlapStyle.amber,
              const Color(0xFFF5E6C8),
            ),
            const SizedBox(height: 10),
            Text('Suncrest surge at 19:00', style: _head(19)),
            const SizedBox(height: 6),
            const Text.rich(
              TextSpan(
                children: [
                  TextSpan(text: 'Without Dr. Okafor: '),
                  TextSpan(
                    text: '1 / 2',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  TextSpan(text: ' coverage. With her: '),
                  TextSpan(
                    text: '2 / 2',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: OverlapStyle.teal,
                    ),
                  ),
                  TextSpan(text: ' coverage.'),
                ],
              ),
            ),
          ],
        ),
      ),
      _cols(
        [
          const _DecisionMatrix(),
          _Card(
            color: const Color(0xFFFAF8F4),
            children: [
              Text('Lead action', style: _head(19)),
              const SizedBox(height: 4),
              const Text(
                'Suncrest Medical Pavilion · 19:00–23:00 ET',
                style: TextStyle(fontSize: 13, color: OverlapStyle.muted),
              ),
              const SizedBox(height: 12),
              if (_decision != null)
                _decision == 'Approved'
                    ? _badge(
                        'Approved · offer sent to Dr. Okafor',
                        OverlapStyle.green,
                        const Color(0xFFDCEBE2),
                      )
                    : _badge(
                        'Rejected · note recorded',
                        OverlapStyle.red,
                        const Color(0xFFF6DCD7),
                      )
              else ...[
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: OverlapStyle.teal,
                    ),
                    onPressed: () => setState(() => _decision = 'Approved'),
                    child: const Text('Approve and send offer'),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: OverlapStyle.red,
                    ),
                    onPressed: _reject,
                    child: const Text('Reject · requires note'),
                  ),
                ),
              ],
            ],
          ),
        ],
        flex: [3, 1],
      ),
      _Card(
        color: const Color(0xFFFAF8F4),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Escalation resolution · CON-2105',
                  style: _head(19),
                ),
              ),
              _badge('Critical', OverlapStyle.red, const Color(0xFFF6DCD7)),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            'Direct clinical override: break off Dr. Kim from video consult CON-2101 and route the Lakeside call.',
          ),
          const SizedBox(height: 12),
          _overridden
              ? _badge(
                  'Override applied',
                  OverlapStyle.green,
                  const Color(0xFFDCEBE2),
                )
              : OutlinedButton(
                  onPressed: () => setState(() => _overridden = true),
                  child: const Text('Apply override'),
                ),
        ],
      ),
    ],
  );
}

class _DecisionMatrix extends StatelessWidget {
  const _DecisionMatrix();
  @override
  Widget build(BuildContext context) => _Card(
    color: const Color(0xFFFAF8F4),
    children: [
      _cardHead(
        '',
        'Decision matrix',
        const Text(
          '6 candidates × 8 rules',
          style: TextStyle(fontSize: 12, color: OverlapStyle.muted),
        ),
      ),
      _table(
        ['Candidate', for (var r = 1; r <= 8; r++) 'R$r'],
        [
          for (final (row, name) in [
            'Okafor',
            'Alvarez',
            'Cho',
            'Haddad',
            'Brennan',
            'Menon',
          ].indexed)
            [
              Text(
                'Dr. $name',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              for (var i = 0; i < 8; i++)
                row == 0 && i < 7
                    ? const Text(
                        '✓',
                        style: TextStyle(
                          color: OverlapStyle.green,
                          fontWeight: FontWeight.w800,
                        ),
                      )
                    : const Text(
                        '–',
                        style: TextStyle(color: OverlapStyle.muted),
                      ),
            ],
        ],
      ),
      const Divider(height: 20),
      const Text.rich(
        TextSpan(
          style: TextStyle(fontSize: 12, color: OverlapStyle.muted),
          children: [
            TextSpan(text: 'Anti-Swamping Guard: effective routing baseline '),
            TextSpan(
              text: '15 consults',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            TextSpan(text: '.'),
          ],
        ),
      ),
    ],
  );
}

// ---------------------------------------------------------------- physician

class _MyShift extends StatelessWidget {
  const _MyShift();
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title('Physician workspace', 'My shift', 'Tuesday 17 March · 18:20 ET'),
      _cols(
        [
          _Card(
            color: const Color(0xFFFAF8F4),
            children: [
              _eyebrow('Shift remaining'),
              const SizedBox(height: 10),
              Text(
                '1 h 36 min',
                style: _head(
                  38,
                  weight: FontWeight.w800,
                  color: OverlapStyle.teal,
                ),
              ),
              const Text(
                'until 20:00 ET',
                style: TextStyle(color: OverlapStyle.muted),
              ),
            ],
          ),
          _Card(
            color: const Color(0xFFFAF8F4),
            children: [
              _eyebrow('Hospitals covered'),
              const SizedBox(height: 8),
              Text('Suncrest · Lakeside · North Valley', style: _head(19)),
              const SizedBox(height: 4),
              const Text(
                '3 active consults',
                style: TextStyle(color: OverlapStyle.muted),
              ),
            ],
          ),
        ],
        flex: [7, 13],
      ),
      _Card(
        color: const Color(0xFFFAF8F4),
        children: [
          Row(
            children: [
              Expanded(child: Text('Active consults', style: _head(19))),
              _badge('On shift', OverlapStyle.teal, const Color(0xFFDDEBEA)),
            ],
          ),
          const SizedBox(height: 10),
          for (final (id, hospital, stage) in const [
            ('CON-2114', 'Suncrest Medical Pavilion', 'Physician call'),
            ('CON-2104', 'Lakeside Medical Center', 'Triaged'),
            ('CON-2113', 'North Valley', 'Imaging'),
          ])
            Container(
              padding: const EdgeInsets.symmetric(vertical: 13),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: OverlapStyle.line)),
              ),
              child: Row(
                children: [
                  SizedBox(
                    width: 92,
                    child: Text(
                      id,
                      style: _mono(
                        13,
                        color: OverlapStyle.ink,
                        weight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Expanded(child: Text(hospital)),
                  _badge(
                    stage,
                    const Color(0xFF3D4853),
                    const Color(0xFFECE8E0),
                  ),
                ],
              ),
            ),
        ],
      ),
    ],
  );
}

class _Offer extends StatefulWidget {
  const _Offer();
  @override
  State<_Offer> createState() => _OfferState();
}

class _OfferState extends State<_Offer> {
  String _status = 'pending';
  int _remaining = 600;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_status != 'pending' || _remaining == 0) return _timer?.cancel();
      setState(() => _remaining--);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final expired = _remaining == 0;
    return Column(
      children: [
        _title('Physician workspace', 'Offers', '1 pending offer'),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Container(
            padding: const EdgeInsets.all(26),
            decoration: const BoxDecoration(
              color: Color(0xFFFAF8F4),
              border: Border(
                top: BorderSide(color: OverlapStyle.teal, width: 4),
                left: BorderSide(color: OverlapStyle.line),
                right: BorderSide(color: OverlapStyle.line),
                bottom: BorderSide(color: OverlapStyle.line),
              ),
              boxShadow: [
                BoxShadow(color: Color(0xFFE8E5DE), offset: Offset(8, 8)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Suncrest Medical Pavilion',
                        style: TextStyle(
                          fontSize: 13,
                          color: OverlapStyle.muted,
                        ),
                      ),
                    ),
                    _badge(
                      'Extra shift',
                      OverlapStyle.amber,
                      const Color(0xFFF5E6C8),
                    ),
                  ],
                ),
                const SizedBox(height: 26),
                Text('Help cover the evening line.', style: _head(28)),
                const SizedBox(height: 20),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text('19:00', style: _head(34, weight: FontWeight.w800)),
                    const Text(
                      '  to  ',
                      style: TextStyle(color: OverlapStyle.muted),
                    ),
                    Flexible(
                      child: Text(
                        '23:00 ET',
                        style: _head(34, weight: FontWeight.w800),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 36),
                const Text(
                  'HIPAA-compliant offer. No patient or consult details are included.',
                  style: TextStyle(fontSize: 13, color: OverlapStyle.muted),
                ),
                const SizedBox(height: 18),
                Container(
                  padding: const EdgeInsets.all(14),
                  color: OverlapStyle.background,
                  child: Row(
                    children: [
                      const Expanded(child: Text('Offer expires in')),
                      Text(
                        expired
                            ? 'Expired'
                            : '${_remaining ~/ 60}:${(_remaining % 60).toString().padLeft(2, '0')}',
                        style: _mono(
                          22,
                          color: OverlapStyle.teal,
                          weight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                if (_status == 'pending' && !expired) ...[
                  FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: OverlapStyle.teal,
                    ),
                    onPressed: () => setState(() => _status = 'accepted'),
                    child: const Text('Accept Extra Shift'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: OverlapStyle.red,
                    ),
                    onPressed: () => setState(() => _status = 'declined'),
                    child: const Text('Decline'),
                  ),
                ] else
                  Container(
                    padding: const EdgeInsets.all(14),
                    color: _status == 'accepted' && !expired
                        ? const Color(0xFFDCEBE2)
                        : const Color(0xFFF6DCD7),
                    child: Text(
                      expired
                          ? 'Expired'
                          : _status == 'accepted'
                          ? 'Accepted'
                          : 'Declined',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        color: _status == 'accepted' && !expired
                            ? OverlapStyle.green
                            : OverlapStyle.red,
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => _toast(
                    context,
                    'Audio is read out by the server in live mode',
                  ),
                  child: const Text('▶ Listen to offer'),
                ),
                TextButton(
                  onPressed: () => openCallDemo(context),
                  child: const Text('Simulate coverage call'),
                ),
                Text(
                  'Offer OFF-1900-SUNCREST · Eastern Time',
                  textAlign: TextAlign.center,
                  style: _mono(11),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _PhysicianSettings extends StatelessWidget {
  const _PhysicianSettings();
  @override
  Widget build(BuildContext context) => Column(
    children: [
      _title('Physician workspace', 'Settings', 'Dr. Priya Shah'),
      _Card(
        color: const Color(0xFFFAF8F4),
        children: [
          Text('Notifications', style: _head(19)),
          const SizedBox(height: 6),
          const Text(
            'Voice previews and offer alerts are enabled for this demo.',
            style: TextStyle(color: OverlapStyle.muted),
          ),
        ],
      ),
    ],
  );
}
