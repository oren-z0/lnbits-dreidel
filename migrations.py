async def m001_initial(db):
    """
    Initial dreidels table.
    """
    await db.execute(
        f"""
        CREATE TABLE dreidel.dreidels (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            secret TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )


async def m002_redux(db):
    """
    Creates an improved dreidels table and migrates the existing data.
    """
    await db.execute("ALTER TABLE dreidel.dreidels RENAME TO dreidels_old")
    await db.execute(
        f"""
        CREATE TABLE dreidel.dreidels (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            url TEXT NOT NULL,
            memo TEXT NOT NULL,
            amount {db.big_int} DEFAULT 0,
            time TIMESTAMP NOT NULL DEFAULT """
        + db.timestamp_now
        + """
        );
    """
    )

    for row in [
        list(row) for row in await db.fetchall("SELECT * FROM dreidel.dreidels_old")
    ]:
        await db.execute(
            """
            INSERT INTO dreidel.dreidels (
                id,
                wallet,
                url,
                memo,
                amount,
                time
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (row[0], row[1], row[3], row[4], row[5], row[6]),
        )

    await db.execute("DROP TABLE dreidel.dreidels_old")
