"""Creates (or reuses) Clerk test users on the preview instance and prints a session token or sign-in ticket.
Usage: python clerk_test_users.py token|ticket admin|member|pending"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
SK = os.environ["CLERK_SECRET_KEY"]
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
USERS = {
    "admin": "leash.admin+clerk_test@example.com",
    "member": "leash.member+clerk_test@example.com",
    "pending": "leash.pending+clerk_test@example.com",
}


def bapi(path, body=None):
    req = urllib.request.Request(
        "https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "emergent-test"})
    return json.load(urllib.request.urlopen(req))


def user_id(role):
    email = USERS[role]
    found = bapi("/users?email_address=" + urllib.parse.quote(email))
    user = found[0] if found else bapi("/users", {"email_address": [email], "password": "Test-pass-12345!", "skip_password_checks": True,
                                                  "first_name": "Test", "last_name": role.title()})
    db.users.update_one({"user_id": user["id"]}, {"$set": {"role": role, "env": "preview", "email": email, "name": f"Test {role.title()}"}}, upsert=True)
    return user["id"]


if __name__ == "__main__":
    kind, role = sys.argv[1], sys.argv[2]
    uid = user_id(role)
    if kind == "token":
        session = bapi("/sessions", {"user_id": uid})
        print(bapi(f"/sessions/{session['id']}/tokens", {"expires_in_seconds": 3600})["jwt"])
    else:
        print(bapi("/sign_in_tokens", {"user_id": uid, "expires_in_seconds": 600})["token"])
