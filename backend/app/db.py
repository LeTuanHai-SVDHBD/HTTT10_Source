import os
from sqlalchemy import create_engine,URL,event
from sqlalchemy.orm import sessionmaker,DeclarativeBase
def database_url():
    if os.getenv('DATABASE_URL'):return os.environ['DATABASE_URL']
    return URL.create('mysql+pymysql',username=os.getenv('MYSQL_USER','httt10_app'),password=os.environ['MYSQL_PASSWORD'],host=os.getenv('MYSQL_HOST','db'),port=int(os.getenv('MYSQL_PORT','3306')),database=os.getenv('MYSQL_DATABASE','httt10'),query={'charset':'utf8mb4'})
engine=create_engine(database_url(),pool_pre_ping=True,isolation_level='READ COMMITTED',hide_parameters=True)
@event.listens_for(engine,'connect')
def utc_session(dbapi_connection,record):
    with dbapi_connection.cursor() as cursor:cursor.execute("SET time_zone = '+00:00'")
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
