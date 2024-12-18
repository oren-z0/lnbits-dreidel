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
            bet_amount {db.big_int} NOT NULL,
            rotate_seconds {db.big_int} NOT NULL,
            players {db.big_int} NOT NULL,
            game_state TEXT NOT NULL,
            payment_hash TEXT NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )
