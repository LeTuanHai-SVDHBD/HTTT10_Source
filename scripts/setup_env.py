from pathlib import Path
import secrets
p=Path(__file__).resolve().parents[1]/'.env'
with p.open('x') as f:
    f.write('MYSQL_ROOT_PASSWORD='+secrets.token_urlsafe(32)+'\nMYSQL_PASSWORD='+secrets.token_urlsafe(32)+'\nJWT_SECRET='+secrets.token_urlsafe(48)+'\n')
print('Created .env with random local secrets. Existing files are never overwritten.')
