"""
Migración: agrega is_admin=False a todos los riders que no tengan el campo.
Ejecutar una sola vez contra la base de datos de producción.

Uso:
  MONGODB_URI=<uri> python scripts/migrate_is_admin.py

Para promover un rider a admin después de la migración:
  MONGODB_URI=<uri> ADMIN_USER_ID=<user_id> python scripts/migrate_is_admin.py --promote
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient


async def main() -> None:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI no definido")
        sys.exit(1)

    client = AsyncIOMotorClient(uri)
    db = client["noray4"]
    riders = db["riders"]

    promote = "--promote" in sys.argv
    admin_user_id = os.environ.get("ADMIN_USER_ID")

    # 1. Migración: pone is_admin=False en todos los que no tengan el campo
    result = await riders.update_many(
        {"is_admin": {"$exists": False}},
        {"$set": {"is_admin": False}},
    )
    print(f"Migración: {result.modified_count} riders actualizados con is_admin=False")

    # 2. Promoción opcional
    if promote:
        if not admin_user_id:
            print("ERROR: ADMIN_USER_ID no definido para --promote")
            client.close()
            sys.exit(1)
        result = await riders.update_one(
            {"user_id": admin_user_id},
            {"$set": {"is_admin": True}},
        )
        if result.modified_count:
            print(f"OK: user_id={admin_user_id} promovido a admin")
        else:
            print(f"WARN: no se encontró rider con user_id={admin_user_id}")

    client.close()


asyncio.run(main())
