"""管理の操作。`uv run python -m v3server.cli grant-admin <利用者>`

つなぎ先と処理ごとの送り先は全作品で共通なので、サーバーの管理者（system:main の admin）だけが変えられる。
最初の管理者は画面から作れないので、ここで付ける。
"""

import argparse
import asyncio

from v3server.database_engine import get_sessionmaker
from v3server.openfga_permissions import Tuple, open_authz


async def grant_admin(user: str, revoke: bool) -> None:
    async with get_sessionmaker()() as session:
        authz = await open_authz(session)
    t = Tuple(f"user:{user}", "admin", "system:main")
    if revoke:
        await authz.write(deletes=[t])
    else:
        await authz.write([t])


def main() -> None:
    parser = argparse.ArgumentParser(prog="v3server.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("grant-admin", help="サーバーの管理者にする")
    p.add_argument("user")
    p.add_argument("--revoke", action="store_true", help="管理者から外す")
    args = parser.parse_args()
    if args.command == "grant-admin":
        asyncio.run(grant_admin(args.user, args.revoke))


if __name__ == "__main__":
    main()
