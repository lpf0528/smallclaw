
import urllib.parse
from typing import List

from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from app.config.db_config import load_db_config_from_dict


def get_engine(conf: dict):
    if conf["name"] == "postgres":
        db_url = f"postgresql+psycopg2://{urllib.parse.quote(conf['user'])}:{urllib.parse.quote(conf['password'])}@{conf['server']}:{conf['port']}/{urllib.parse.quote(conf['db'])}"
        return create_engine(db_url,
                             connect_args={"options": f"-c search_path={conf.dbSchema}", "connect_timeout": conf.timeout},
                             pool_timeout=conf.timeout)

    return create_engine(f"sqlite://{urllib.parse.quote(conf['path'])}")


def get_engine_conn():
    conf = load_db_config_from_dict()[0]
    engine = get_engine(conf)
    return engine


def get_data_engine():
    engine = get_engine_conn()
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


def insert_data(session, table_name: str, fields: List[any], data: List[any]):
    engine = get_engine_conn()
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        stmt = table.insert().values(data)
        conn.execute(stmt)
        conn.commit()
