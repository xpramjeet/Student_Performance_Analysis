from getpass import getpass
from werkzeug.security import generate_password_hash
from backend.database.database import get_db_connection

p = getpass("Naya password enter karo: ")
q = getpass("Naya password enter karo: ")

print("Password length:", len(p.strip()))

if len(p.strip()) < 8:
    print("Password kam se kam 8 characters ka rakho.")
elif p != q:
    print("Passwords match nahi hue.")
else:
    db = get_db_connection()
    c = db.cursor()
    c.execute(
        "UPDATE users SET password=%s WHERE username=%s",
        (generate_password_hash(p), "admin")
    )
    db.commit()
    print("Admin password updated." if c.rowcount == 1 else "Admin account nahi mila.")
    c.close()
    db.close()
