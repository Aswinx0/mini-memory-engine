import sqlite3
from memory_engine.db import init_db

init_db("test.db")
print(sqlite3.connect("test.db").execute("select name from sqlite_master").fetchall())