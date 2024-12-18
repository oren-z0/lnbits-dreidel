async def m001_initial(db):
    """
    Initial dreidels table.
    """
    await db.execute(
        f"""
        CREATE TABLE dreidel.dreidels (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
