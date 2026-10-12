from backend.database.database import get_db_connection

db = get_db_connection()
c = db.cursor()

c.execute("""
ALTER TABLE students
ADD COLUMN university_roll_no VARCHAR(30) NULL
""")

db.commit()
print("University Roll Number column added successfully")

c.close()
db.close()
