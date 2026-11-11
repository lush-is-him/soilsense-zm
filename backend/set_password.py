"""Change a user's password.

    python -m backend.set_password admin

Asks for the new password twice. Run it on the laptop that holds the database.
"""

import getpass
import sys

from backend.auth import hash_password
from backend.db import connect, migrate


def set_password(conn, username, password):
    if len(password) < 8:
        raise ValueError("the password must be at least 8 characters")
    with conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                           (hash_password(password), username))
    if cur.rowcount == 0:
        raise ValueError(f"no user called {username!r}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Type it again: "):
        print("The two passwords are different. Nothing changed.")
        return 1
    conn = connect()
    migrate(conn)
    try:
        set_password(conn, argv[0], first)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Password changed for {argv[0]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
