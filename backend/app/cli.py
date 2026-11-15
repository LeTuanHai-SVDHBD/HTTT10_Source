import argparse,getpass,json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text,inspect,select
from alembic.config import Config
from alembic import command
from .db import engine,Session
from .models import User,UserRole
from .security import HASHER
from .services import audit
def config():return Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['migrate','adopt-baseline','bootstrap','expire-proposals']);a=p.parse_args()
    if a.action=='expire-proposals':
        from .scheduling import expire_due
        print('Expired proposals:',expire_due());return
    if a.action=='migrate':command.upgrade(config(),'head');print('Migration complete.');return
    if a.action=='adopt-baseline':
        expected=json.loads((Path(__file__).resolve().parents[1]/'db/schema_metadata.json').read_text());i=inspect(engine)
        for table in expected:
            assert i.has_table(table['name']), 'Missing table '+table['name']
            assert {c['name'] for c in i.get_columns(table['name'])}=={c['name'] for c in table['columns']},'Columns differ: '+table['name']
            assert set(i.get_pk_constraint(table['name'])['constrained_columns'])==set(table['pk']),'PK differs'
            actual={tuple(x['column_names']) for x in i.get_unique_constraints(table['name'])}|{tuple(x['column_names']) for x in i.get_indexes(table['name']) if x['unique']}
            assert {tuple(x) for x in table['uniques']}<=actual,'Unique indexes differ'
            actual_fk={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in i.get_foreign_keys(table['name'])}
            expected_fk={(tuple(cs),target,tuple(rs)) for cs,target,rs in table['fks']}
            if table['name']=='schedule_roots':expected_fk.add((('id','current_revision_id'),'schedule_revisions',('schedule_id','id')))
            assert actual_fk==expected_fk,'FK differs: '+table['name']
            assert {'ck_'+n for n,_ in table['checks']}<={x['name'] for x in i.get_check_constraints(table['name'])},'CHECK differs'
        assert {'v_effective_schedules','v_effective_meetings','v_effective_participants'}<=set(i.get_view_names()),'Missing views'
        with engine.connect() as c:assert c.scalar(text("SELECT COUNT(*) FROM schema_migrations WHERE version='001_baseline'"))==1
        command.stamp(config(),'head');print('Adopted existing baseline; no business rows changed.');return
    email=input('Email Admin: ').strip().lower()
    from pydantic import TypeAdapter,EmailStr
    email=str(TypeAdapter(EmailStr).validate_python(email))
    password=getpass.getpass('Temporary password (12-128 characters): ')
    if not 12<=len(password)<=128 or password!=getpass.getpass('Confirm password: '):raise SystemExit('Password length/confirmation invalid')
    with Session.begin() as db:
        dept=db.scalar(text("SELECT id FROM departments WHERE code='HC' FOR UPDATE"))
        if not dept:raise SystemExit('Run baseline + seed first')
        if db.scalar(text("SELECT COUNT(*) FROM user_roles r JOIN users u ON r.user_id=u.id WHERE r.role='ADMIN' AND u.status='ACTIVE'")):raise SystemExit('An active Admin already exists; bootstrap refused')
        u=User(id=str(uuid4()),employee_code='ADMIN001',full_name='Quản trị hệ thống',email=email,department_id=dept,status='ACTIVE',password_hash=HASHER.hash(password),must_change_password=True,auth_version=1,row_version=1)
        db.add(u);db.flush();db.add(UserRole(user_id=u.id,role='ADMIN',granted_by=u.id));audit(db,u.id,'BOOTSTRAP_ADMIN')
    print('Admin created. Change temporary password at first login.')
if __name__=='__main__':main()
