import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/live/backend_auth.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/backend_auth_gate.dart';

Map<String, Object?> user(String role) => {
  'email': 'person@example.test',
  'name': 'Test account',
  'role': role,
  'role_label': role == 'lead' ? 'Clinical lead' : role,
  'physician_id': role == 'physician' ? 'PHY-009' : null,
};
http.Response jsonResponse(Object body, [int status = 200]) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

void main() {
  for (final role in ['lead', 'physician', 'coordinator']) {
    test('backend identity parses $role without invented workflow fields', () {
      expect(BackendUser.parse(user(role)).role, role);
    });
  }
  test('unknown roles and malformed physician identities fail', () {
    expect(() => BackendUser.parse(user('admin')), throwsA(isA<ParseError>()));
    expect(
      () => BackendUser.parse({...user('physician'), 'physician_id': null}),
      throwsA(isA<ParseError>()),
    );
  });

  testWidgets('wrong password shows backend detail; success signs in and out', (
    tester,
  ) async {
    final browser = MemoryBrowser();
    final requests = <http.Request>[];
    var wrong = true;
    final auth = BackendAuthRepository(
      Uri.parse('http://localhost:8000'),
      browser: browser,
      httpClient: MockClient((request) async {
        requests.add(request);
        if (!['/auth/login', '/auth/me'].contains(request.url.path)) {
          expect(request.headers['authorization'], 'Bearer test-session');
          return jsonResponse({'detail': 'Not Found'}, 404);
        }
        if (request.url.path == '/auth/login') {
          expect(jsonDecode(request.body), {
            'email': 'person@example.test',
            'password': 'test-password',
          });
          return wrong
              ? jsonResponse({'detail': 'Email or password is incorrect.'}, 401)
              : jsonResponse({
                  'token': 'test-session',
                  'expires_at': 2000000000,
                  'user': user('lead'),
                });
        }
        expect(request.url.path, '/auth/me');
        expect(request.headers['authorization'], 'Bearer test-session');
        return jsonResponse({'user': user('lead')});
      }),
    );
    addTearDown(auth.dispose);
    await tester.pumpWidget(SevaroApp(home: BackendAuthGate(repository: auth)));
    await tester.pumpAndSettle();
    expect(find.text('I work as'), findsNothing);
    expect(find.byType(ChoiceChip), findsNothing);
    expect(
      find.text("Access is based on your account's role."),
      findsOneWidget,
    );
    await tester.enterText(
      find.byType(TextFormField).first,
      'person@example.test',
    );
    await tester.enterText(find.byType(TextFormField).last, 'test-password');
    await tester.ensureVisible(find.text('Sign in'));
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Email or password is incorrect.'), findsOneWidget);
    expect(browser.session['sevaro_token'], isNull);
    expect(
      tester
          .widget<TextFormField>(find.byType(TextFormField).first)
          .controller!
          .text,
      'person@example.test',
    );
    wrong = false;
    await tester.enterText(find.byType(TextFormField).last, 'test-password');
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Approvals'), findsWidgets);
    expect(find.text('Coverage'), findsWidgets);
    expect(find.text('My shift'), findsNothing);
    await tester.tap(find.text('Account').last);
    await tester.pumpAndSettle();
    expect(find.text('Signed in to the backend'), findsOneWidget);
    expect(find.text('Clinical lead account'), findsOneWidget);
    expect(find.text('Clinical lead'), findsOneWidget);
    expect(requests.where((r) => r.url.path == '/auth/me'), isNotEmpty);
    await tester.ensureVisible(find.text('Sign out'));
    await tester.tap(find.text('Sign out'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(browser.session['sevaro_token'], isNull);
    await tester.pumpWidget(const SizedBox());
    auth.dispose();
  });

  testWidgets('stored session restores and a subsequent 401 signs out', (
    tester,
  ) async {
    final browser = MemoryBrowser()..session['sevaro_token'] = 'stored';
    var expired = false;
    final auth = BackendAuthRepository(
      Uri.parse('http://localhost:8000'),
      browser: browser,
      httpClient: MockClient((request) async {
        if (request.url.path != '/auth/me') {
          return jsonResponse({'detail': 'Not Found'}, 404);
        }
        expect(request.url.path, '/auth/me');
        return expired
            ? jsonResponse({'detail': 'Sign in to continue.'}, 401)
            : jsonResponse({'user': user('physician')});
      }),
    );
    addTearDown(auth.dispose);
    await tester.pumpWidget(SevaroApp(home: BackendAuthGate(repository: auth)));
    await tester.pumpAndSettle();
    expect(find.text('My shift'), findsWidgets);
    expect(find.text('Offers'), findsWidgets);
    expect(find.text('Approvals'), findsNothing);
    expect(find.text('Coverage'), findsNothing);
    await tester.tap(find.text('Account').last);
    await tester.pumpAndSettle();
    expect(find.text('Signed in to the backend'), findsOneWidget);
    expect(find.text('Physician ID: PHY-009'), findsOneWidget);
    expect(find.text('Physician account'), findsOneWidget);
    expect(find.text('Clinical lead account'), findsNothing);
    expect(find.text('Open workflow demo'), findsNothing);
    expect(find.text('Open working demo'), findsNothing);
    expect(find.text('Preview screens'), findsNothing);
    expect(find.text('Check session'), findsOneWidget);
    expired = true;
    await tester.ensureVisible(find.text('Check session'));
    await tester.tap(find.text('Check session'));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Please sign in again.'), findsOneWidget);
    expect(browser.session['sevaro_token'], isNull);
    await tester.pumpWidget(const SizedBox());
    auth.dispose();
  });

  testWidgets(
    'connection failure retains stored session and retry restores it',
    (tester) async {
      final browser = MemoryBrowser()..session['sevaro_token'] = 'stored';
      var offline = true;
      final auth = BackendAuthRepository(
        Uri.parse('http://localhost:8000'),
        browser: browser,
        httpClient: MockClient((request) async {
          if (offline) throw http.ClientException('offline');
          if (request.url.path != '/auth/me') {
            return jsonResponse({'detail': 'Not Found'}, 404);
          }
          return jsonResponse({'user': user('lead')});
        }),
      );
      addTearDown(auth.dispose);
      await tester.pumpWidget(
        SevaroApp(home: BackendAuthGate(repository: auth)),
      );
      await tester.pumpAndSettle();
      expect(find.text("Can't reach Sevaro"), findsOneWidget);
      expect(browser.session['sevaro_token'], 'stored');
      offline = false;
      await tester.tap(find.text('Retry session'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Account').last);
      await tester.pumpAndSettle();
      expect(find.text('Signed in to the backend'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      auth.dispose();
    },
  );

  test('late 401 from an old token cannot clear a newer sign-in', () async {
    final browser = MemoryBrowser()..session['sevaro_token'] = 'old';
    final delayed = Completer<http.Response>();
    final auth = BackendAuthRepository(
      Uri.parse('http://localhost:8000'),
      browser: browser,
      httpClient: MockClient((request) async {
        if (request.method == 'GET') return delayed.future;
        return jsonResponse({
          'token': 'new',
          'expires_at': 2000000000,
          'user': user('lead'),
        });
      }),
    );
    addTearDown(auth.dispose);
    final restore = auth.currentUser();
    await auth.signIn('person@example.test', 'test-password');
    delayed.complete(jsonResponse({'detail': 'Expired'}, 401));
    await restore;
    expect(browser.session['sevaro_token'], 'new');
    expect(auth.user.value?.role, 'lead');
  });

  testWidgets('coordinator sees web dashboard guidance without mobile feeds', (
    tester,
  ) async {
    final browser = MemoryBrowser()..session['sevaro_token'] = 'stored';
    final paths = <String>[];
    final auth = BackendAuthRepository(
      Uri.parse('http://localhost:8000'),
      browser: browser,
      httpClient: MockClient((request) async {
        paths.add(request.url.path);
        return jsonResponse({'user': user('coordinator')});
      }),
    );
    addTearDown(auth.dispose);
    await tester.pumpWidget(SevaroApp(home: BackendAuthGate(repository: auth)));
    await tester.pumpAndSettle();
    expect(find.text('Use the web dashboard'), findsOneWidget);
    expect(find.text('My shift'), findsNothing);
    expect(find.text('Approvals'), findsNothing);
    expect(paths, isNotEmpty);
    expect(paths, everyElement('/auth/me'));
    await tester.pumpWidget(const SizedBox());
    auth.dispose();
  });

  testWidgets('physician dashboard renders shift data from authenticated API', (
    tester,
  ) async {
    final browser = MemoryBrowser()..session['sevaro_token'] = 'stored';
    final shift = jsonDecode(
      File('assets/contracts/mobile_shift_on.json').readAsStringSync(),
    );
    final auth = BackendAuthRepository(
      Uri.parse('http://localhost:8000'),
      browser: browser,
      httpClient: MockClient((request) async {
        expect(request.headers['authorization'], 'Bearer stored');
        if (request.url.path == '/auth/me') {
          return jsonResponse({'user': user('physician')});
        }
        if (request.url.path == '/me/shift') return jsonResponse(shift);
        return jsonResponse({'detail': 'Not Found'}, 404);
      }),
    );
    addTearDown(auth.dispose);
    await tester.pumpWidget(SevaroApp(home: BackendAuthGate(repository: auth)));
    await tester.pumpAndSettle();
    expect(find.text('Test account'), findsOneWidget);
    expect(find.textContaining('CON-2113'), findsWidgets);
    expect(find.text('Approvals'), findsNothing);
    await tester.pumpWidget(const SizedBox());
    auth.dispose();
  });
}
