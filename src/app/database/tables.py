from asyncpg import Connection


async def create_database_tables(conn: Connection):
    try:
        await create_feature_films_table(conn)
        await create_series_table(conn)
        await create_mini_series_table(conn)
        await create_favorites_table(conn)
        await create_users_table(conn)
        await create_channels_table(conn)
        await create_bots_table(conn)
    except Exception as e:
        print("ERROR", e)


async def create_users_table(conn: Connection):
    query = """
        CREATE TABLE IF NOT EXISTS users (
            tg_id BIGINT PRIMARY KEY NOT NULL,
            username TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL

        )
    """
    await conn.execute(query)


async def create_channels_table(conn: Connection):
    query = """ 
        CREATE TABLE IF NOT EXISTS channels(
            channel_id BIGINT PRIMARY KEY NOT NULL,
            channel_name TEXT NOT NULL,
            channel_username TEXT,
            channel_status TEXT NOT NULL,
            message TEXT,
            channel_url TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
    """
    await conn.execute(query)

async def create_bots_table(conn: Connection) -> None:
    query = """
        CREATE TABLE IF NOT EXISTS bots(
            bot_name TEXT NOT NULL,
            bot_username TEXT NOT NULL,
            bot_status TEXT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
    """

    await conn.execute(query)

async def create_feature_films_table(conn: Connection):
    query = """
        CREATE TABLE IF NOT EXISTS feature_films(
            code BIGINT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            video_file_id TEXT NOT NULL,
            captions TEXT
        );
    """
    await conn.execute(query)


async def create_series_table(conn: Connection):
    query = """
        CREATE TABLE IF NOT EXISTS series(
            code BIGINT NOT NULL,
            name TEXT NOT NULL,
            season BIGINT NOT NULL,
            series BIGINT NOT NULL,
            video_file_id TEXT NOT NULL,
            captions TEXT,
            PRIMARY KEY (code, season, series)
        );
    """
    await conn.execute(query)


async def create_mini_series_table(conn: Connection):
    query = """
        CREATE TABLE IF NOT EXISTS mini_series(
            code BIGINT NOT NULL,
            name TEXT NOT NULL,
            series BIGINT NOT NULL,
            video_file_id TEXT NOT NULL,
            captions TEXT,
            PRIMARY KEY (code, series)
        );
    """
    await conn.execute(query)

async def create_favorites_table(conn: Connection):
    query = """
        CREATE TABLE IF NOT EXISTS favorites(
            user_id BIGINT NOT NULL,
            movie_code BIGINT NOT NULL,
            PRIMARY KEY (user_id, movie_code)
        );
    """
    await conn.execute(query)