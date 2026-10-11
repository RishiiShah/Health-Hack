"""Disposable localhost browser fixture. Run with backend/.venv/bin/python.

Source CSVs remain local and must match the official kit. CC_E2E_PASSWORD supplies
only these test accounts' password. State is saved outside the repo for restart
verification; --cleanup drops only this fixture's generated database.
"""
import argparse
from dataclasses import replace
from datetime import date
import json
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def local_admin_url(value):
    from psycopg.conninfo import conninfo_to_dict
    parts = conninfo_to_dict(value)
    if parts.get('host') not in {'127.0.0.1', 'localhost', '::1'} or parts.get('dbname') != 'postgres':
        raise ValueError('E2E database creation requires an explicit localhost postgres admin database')
    return value


def checked_state(config, admin_url):
    from psycopg.conninfo import conninfo_to_dict
    expected = conninfo_to_dict(admin_url)
    actual = conninfo_to_dict(config['url'])
    if (not config['dbname'].startswith('cc_browser_e2e_') or actual.get('dbname') != config['dbname']
            or actual.get('host') != expected.get('host') or actual.get('port', '5432') != expected.get('port', '5432')):
        raise ValueError('E2E state must identify this localhost fixture database')
    return config


def main():
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=ROOT/'data')
    parser.add_argument('--port', type=int, default=8012)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError('port must be between 1 and 65535')
    state_path = args.state.resolve()
    if state_path.is_relative_to(ROOT):
        raise ValueError('E2E state contains secrets and must be outside the repository')
    admin = local_admin_url(os.getenv('CC_E2E_PG_ADMIN_URL', 'postgresql://postgres:postgres@127.0.0.1:5432/postgres'))
    config = checked_state(json.loads(state_path.read_text()), admin) if state_path.exists() else None
    if args.cleanup:
        if config:
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(config['dbname'])))
            state_path.unlink()
        print('Disposable browser database and state removed.')
        return
    password = os.environ.get('CC_E2E_PASSWORD', '')
    if not 8 <= len(password) <= 1024:
        raise ValueError('CC_E2E_PASSWORD must contain 8–1024 characters')
    from app.config import OFFICIAL_REFERENCE_FINGERPRINT
    from app.service import REFERENCE_FILES, reference_manifest, references_from_files
    source = {'name':'Sevaro official reference kit','service_date':'2026-03-17',
              'files':{name:(args.references/name).read_text(encoding='utf-8-sig') for name in REFERENCE_FILES}}
    if reference_manifest(source)['fingerprint'] != OFFICIAL_REFERENCE_FINGERPRINT:
        raise ValueError('Browser fixture requires the unchanged official reference kit')
    references_from_files(source['files'], date.fromisoformat(source['service_date']))  # validate before creating a database
    if config is None:
        dbname = 'cc_browser_e2e_' + uuid4().hex
        config = {'dbname':dbname,'url':make_conninfo(admin,dbname=dbname),'secret':secrets.token_hex(32)}
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
        try:
            descriptor = os.open(state_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(descriptor,'w') as handle:
                json.dump(config,handle)
        except BaseException:
            with psycopg.connect(admin,autocommit=True) as conn:
                conn.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(dbname)))
            raise
    from app import main as application
    from app.auth import Accounts, Auth
    from app.passwords import hash_password
    application.settings = replace(application.settings, reference_dir=str(args.references.resolve()),
        service_date='2026-03-17',clock_mode='fixed',clock_fixed='2026-03-17T18:20:00-04:00',offer_history=None)
    users = [{'email':email,'name':name,'role':role,**({'physician_id':pid} if pid else {}),'password_hash':hash_password(password)}
             for email,name,role,pid in [('coord@e2e.local','E2E Coordinator','coordinator',None),
                  ('lead@e2e.local','E2E Lead','lead',None),('physician@e2e.local','E2E Physician','physician','PHY-009'),
                  ('other@e2e.local','Other Physician','physician','PHY-014')]]
    api = application.create_app(database_url=config['url'], sweep_s=0,
        auth=Auth(accounts=Accounts(json.dumps(users),config['secret'])),
        speech=SimpleNamespace(available=False,conn=SimpleNamespace(close=lambda:None)))
    print(f'Disposable E2E server on localhost:{args.port}; references pinned; external speech disabled.',flush=True)
    import uvicorn
    uvicorn.run(api,host='127.0.0.1',port=args.port,log_level='warning')


if __name__ == '__main__':
    main()
