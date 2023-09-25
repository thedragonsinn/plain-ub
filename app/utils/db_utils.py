def extract_user_data(user) -> dict:
    return dict(
        name=f"""{user.first_name or ""} {user.last_name or ""}""",
        username=user.username,
        mention=user.mention,
    )


async def add_data(collection, id: int | str, data: dict) -> None:
    found = await collection.find_one({"_id": id})
    if not found:
        await collection.insert_one({"_id": id, **data})
    else:
        await collection.update_one({"_id": id}, {"$set": data})


async def delete_data(collection, id: int | str) -> bool | None:
    found = await collection.find_one({"_id": id})
    if found:
        await collection.delete_one({"_id": id})
        return True
